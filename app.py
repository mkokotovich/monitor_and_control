#!/usr/bin/env python
from flask import Flask, render_template, session, request, url_for
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, \
    close_room, rooms, disconnect

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = "eventlet"

page_title = "Control the Lights"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        # Do the work of reading images and uploading them to the cloud here
        # Then brodcast out a new image url
        # See http://cloudinary.com/documentation/django_image_upload#server_side_upload
        socketio.sleep(10)
        count += 1
        socketio.emit('my_response',
                      {'data': 'Server generated event', 'count': count}, namespace='')


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode, page_title=page_title)


class MyNamespace(Namespace):

    def on_update_request(self):
        session['receive_count'] = session.get('receive_count', 0) + 1
        if session['receive_count'] % 2 == 0:
            img_src = "lights.jpg"
        else:
            img_src = "lights2.jpg"
        emit('picture_update',
            {'count': session['receive_count'], 'source': "static/" + img_src})

    def on_connect(self):
        global thread
        if thread is None:
            thread = socketio.start_background_task(target=background_thread)


socketio.on_namespace(MyNamespace(''))


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=8080)

