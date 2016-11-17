#!/usr/bin/env python
from flask import Flask, render_template, session, request, url_for
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
import urllib2
import datetime

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

    def __init__(self):
        self.last_image_url = "http://res.cloudinary.com/cloudmedia/image/upload/v1478798030/stream-unavailable.jpg"
        self.last_update_time = "never"
        self.camera_server = "http://192.168.86.106:8080"
        self.filename = "images/image_latest.jpg"

    def refresh_image(self):
        image_url = self.last_image_url
        # TODO: limit refresh to a certain rate
        try:
            # Grab the latest frame from the camera
            request = urllib2.urlopen(self.camera_server + "/photo.jpg", timeout=10)
            with open(self.filename, 'wb') as f:
                f.write(request.read())
            # Upload the image to the cloud
            upload_result = upload(self.filename)
            if upload_result:
                # If the upload was successful, save the result in last_image_url
                image_url = upload_result['url']
                self.last_image_url = image_url
                self.last_update_time = datetime.datetime.now().strftime('%H:%M:%S')
            else:
                image_url = self.last_image_url
        except Exception as e:
            print "Failed to refresh image " + str(e)
            image_url = self.last_image_url
        return image_url


def background_thread(imageUpdater):
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(15)
        img_url = imageUpdater.refresh_image()
        socketio.emit('picture_update',
                {'source': img_url, 'picture_msg': "Last update: " + imageUpdater.last_update_time},
                namespace='')


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode, page_title=page_title)


class MyNamespace(Namespace):
    imageUpdater = None

    def __init__(self, ns, imageUpdater):
        super(MyNamespace, self).__init__(ns)
        self.imageUpdater = imageUpdater

    def on_update_request(self):
        global last_image_url
        global last_update_time
        img_url = self.imageUpdater.refresh_image() #add force=True
        emit('picture_update',
            {'source': img_url,
             'picture_msg': "Last update: " + last_update_time})

    def on_turn_off_request(self):
        emit('toggle_result',
            {'status': "success",
             'operation': "turn off",
             'status_msg': "Successfully turned off light, image will auto-update"})

    def on_turn_on_request(self):
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
            thread = socketio.start_background_task(target=background_thread, imageUpdater=self.imageUpdater)


imageUpdater = ImageUpdater()

socketio.on_namespace(MyNamespace(ns='', imageUpdater=imageUpdater))


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=8080)

