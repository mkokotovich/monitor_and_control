#!/usr/bin/env python
from flask import Flask, render_template, session, request, url_for
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
import urllib

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = "eventlet"

page_title = "Control the Lights"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
camera_server = "http://192.168.86.106:8080"
image_number = 0
filename = "images/image_latest.jpg"

def refresh_image(filename):
    # TODO: limit refresh to a certain rate
    # Grab the latest frame from the camera
    urllib.urlretrieve("{}{}".format(camera_server, "/photo.jpg"), filename)
    # Upload the image to the cloud
    upload_result = upload(filename)
    if upload_result:
        image_url = upload_result['url']
    else:
        image_url = None
    # Return the url of the new image
    return image_url


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        socketio.sleep(15)
        img_url = refresh_image(filename)
        socketio.emit('picture_update',
            {'source': img_url},
            namespace='')


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode, page_title=page_title)


class MyNamespace(Namespace):

    def on_update_request(self):
        img_url = refresh_image(filename) #add force=True
        emit('picture_update',
            {'source': img_url})

    def on_connect(self):
        img_url = refresh_image(filename)
        emit('picture_update',
            {'source': img_url})
        global thread
        if thread is None:
            thread = socketio.start_background_task(target=background_thread)


socketio.on_namespace(MyNamespace(''))


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=8080)

