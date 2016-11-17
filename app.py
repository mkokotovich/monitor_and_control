#!/usr/bin/env python
from flask import Flask, render_template, session, request, url_for
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
import urllib2
import datetime
import threading

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = "eventlet"

page_title = "Control the Lights"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None

class ImageUpdater:
    filename = "images/image_latest.jpg"
    camera_server = "http://192.168.86.106:8080"
    last_image_url = "http://res.cloudinary.com/cloudmedia/image/upload/v1478798030/stream-unavailable.jpg"
    last_update_time = "never"
    last_refresh_attempt = datetime.datetime.min
    refresh_interval = datetime.timedelta(seconds=10)

    def __init__(self):
        self.last_image_url = "http://res.cloudinary.com/cloudmedia/image/upload/v1478798030/stream-unavailable.jpg"
        self.last_update_time = "never"
        self.camera_server = "http://192.168.86.106:8080"
        self.filename = "images/image_latest.jpg"
        self.last_refresh_attempt = datetime.datetime.min
        self.refresh_interval = datetime.timedelta(seconds=5)

    def refresh_image(self):
        if self.last_refresh_attempt + self.refresh_interval > datetime.datetime.now():
            print "+++ImageUpdater+++: Skipping this update"
            # Return right away if we need to wait longer
            return
        self.last_refresh_attempt = datetime.datetime.now()
        try:
            # Grab the latest frame from the camera
            request = urllib2.urlopen(self.camera_server + "/photo.jpg", timeout=10)
            with open(self.filename, 'wb') as f:
                f.write(request.read())
            # Upload the image to the cloud
            upload_result = upload(self.filename)
            if upload_result:
                # If the upload was successful, save the result in last_image_url
                self.last_image_url = upload_result['url']
                self.last_update_time = datetime.datetime.now().strftime('%H:%M:%S')
        except Exception as e:
            print "+++ImageUpdater+++: Failed to refresh image " + str(e)


def image_refresh_thread(threadImageUpdater):
    print "---thread---: Calling refresh_image"
    threadImageUpdater.refresh_image()


def background_image_updater(**kwargs):
    backgroundUpdateEvent = kwargs["backgroundUpdateEvent"]
    backgroundImageUpdater = kwargs["backgroundImageUpdater"]

    time_to_wait_before_refresh = 15
    print "---background---: background_image_updater started"
    while True:
        # Wait time_to_wait_before_refresh seconds or until someone calls backgroundUpdateEvent.set()
        time_waited = 0
        while time_waited < time_to_wait_before_refresh and not backgroundUpdateEvent.is_set():
            socketio.sleep(1)
            time_waited += 1
        print "---background---: refreshing image"
        # Clear event right away, so if another set comes in we catch it
        backgroundUpdateEvent.clear()
        # Update the image in a new thread, so the UI still responds
        thread = threading.Thread(target=image_refresh_thread, args = (backgroundImageUpdater, ))
        thread.start()
        while thread.is_alive():
            socketio.sleep(1)
        thread.join()
        socketio.emit('picture_update',
                {'source': backgroundImageUpdater.last_image_url, 'picture_msg': "Last update: " + backgroundImageUpdater.last_update_time},
                namespace='')


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode, page_title=page_title)


class MyNamespace(Namespace):
    imageUpdater = None
    updateEvent = None

    def __init__(self, ns, nsImageUpdater, nsUpdateEvent):
        super(MyNamespace, self).__init__(ns)
        self.imageUpdater = nsImageUpdater
        self.updateEvent = nsUpdateEvent

    def on_update_request(self):
        self.updateEvent.set()
        print "Update request received, signaled thread for update"
        emit('picture_update',
            {'source': self.imageUpdater.last_image_url,
             'picture_msg': "Last update: " + self.imageUpdater.last_update_time})

    def on_turn_off_request(self):
        self.updateEvent.set()
        emit('toggle_result',
            {'status': "success",
             'operation': "turn off",
             'status_msg': "Successfully turned off light, image will auto-update"})

    def on_turn_on_request(self):
        self.updateEvent.set()
        emit('toggle_result',
            {'status': "success",
             'operation': "turn on",
             'status_msg': "Successfully turned on light, image will auto-update"})

    def on_connect(self):
        emit('picture_update',
            {'source': self.imageUpdater.last_image_url,
             'picture_msg': "Last update: " + self.imageUpdater.last_update_time})
        global thread
        if thread is None:
            print "Starting thread"
            thread = socketio.start_background_task(target=background_image_updater, backgroundImageUpdater=self.imageUpdater, backgroundUpdateEvent=self.updateEvent)
        self.updateEvent.set()


g_imageUpdater = ImageUpdater()
g_updateEvent = threading.Event()

socketio.on_namespace(MyNamespace(ns='', nsImageUpdater=g_imageUpdater, nsUpdateEvent=g_updateEvent))


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=8080)

