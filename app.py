import pickle
import cv2
import numpy as np
import mediapipe as mp
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import mysql.connector
import base64
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize MediaPipe Hands and Drawing utilities
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Load the trained model and scaler
with open(r'C:\Users\91813\Downloads\SIGNLINGO-FINAL-main\SIGNLINGO-FINAL-main\model.p', 'rb') as f:
    model_data = pickle.load(f)
    model = model_data['model']
    scaler = model_data['scaler']

# Function to extract hand landmarks from an image
def extract_hand_landmarks(image):
    data_aux = []

    # Convert image from BGR to RGB
    img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Process the image to detect hand landmarks
    with mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5) as hands:
        results = hands.process(img_rgb)
    
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            for landmark in hand_landmarks.landmark:
                data_aux.append(landmark.x)
                data_aux.append(landmark.y)
                data_aux.append(landmark.z)
            mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    else:
        return None, image

    # Ensure data_aux has a fixed length
    if len(data_aux) < 21 * 3:
        data_aux.extend([0] * (21 * 3 - len(data_aux)))
    elif len(data_aux) > 21 * 3:
        data_aux = data_aux[:21 * 3]
    
    return np.array(data_aux).reshape(1, -1), image

# Database connection setup
def connect_db():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="ArteryNoir#5",
        database="aarathi"
    )
    return connection

# Function to get the image path from the database
def get_image_data(label, output_language):
    connection = connect_db()
    cursor = connection.cursor()
    label_str = str(label)
    query = "SELECT isl_img FROM translation_table WHERE label = %s" if output_language == 'isl' else "SELECT asl_img FROM translation_table WHERE label = %s"
    cursor.execute(query, (label_str,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    if result and result[0]:
        # Convert BLOB to base64 string
        img_blob = result[0]
        img_base64 = base64.b64encode(img_blob).decode('utf-8')
        return img_base64
    return None


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/translation')
def translation():
    return render_template('translation.html')


@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('frame')
def handle_frame(data):
    start_time = time.time()
    
    img_data = base64.b64decode(data['image'])
    output_language = data['output_language']
    nparr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    landmarks, annotated_image = extract_hand_landmarks(frame)
    
    if landmarks is not None:
        landmarks = scaler.transform(landmarks)
        prediction = model.predict(landmarks)
        label = prediction[0]
        image_data = get_image_data(label, output_language)
    else:
        label = 'No hand detected'
        image_data = None

    _, buffer = cv2.imencode('.jpg', annotated_image)
    img_str = base64.b64encode(buffer).decode('utf-8')
    emit('response_frame', {'image': img_str, 'label': label, 'image_data': image_data})

    end_time = time.time()
    print(f"Frame processed in {end_time - start_time:.2f} seconds")

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
