from flask import Flask, redirect, request, jsonify, render_template, send_file, url_for
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from speechbrain.pretrained import EncoderClassifier
from flask_pymongo import PyMongo
import torch
import librosa
import soundfile as sf
import os
from bson import ObjectId

import certifi
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)

uri = "mongodb+srv://ishtee:ishtee@voicechat.8b7vo.mongodb.net/?retryWrites=true&w=majority&appName=VoiceChat"

# Create a new client and connect to the server
client = MongoClient(uri, tlsCAFile=certifi.where(), server_api=ServerApi('1'))

db = client.profiles

# Load models
processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
tts_model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")
speaker_model = EncoderClassifier.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", run_opts={"device": "cpu"})

# Load speaker embeddings
# waveform, sample_rate = librosa.load("feba.wav", sr=16000)  # Load sample voice
# waveform = librosa.util.normalize(waveform)
# embeddings = speaker_model.encode_batch(torch.tensor([waveform]))
# speaker_embeddings = embeddings.squeeze(0)

# Initialize LangChain model
template = """
You have to imitate that you are a friend of the user. Act like the user's friend and make use of the given personality of the friend so that you can generate responses that are very close to how the user's friend would react in real life.

Here is the conversation history: {message_history}

This is the personality of the friend: {description}

A user just said: {user_input}

Generate a response which imitates how the user's friend would talk to him in real life according to the personality of the friend and the history of the conversation. A short message of 5 to 10 words is recommended.
"""
model = OllamaLLM(model="llama3.2")
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

# Conversation context
message_history = ""



@app.route("/")
def index():
    return render_template('index.html')

# @app.route('/process_audio', methods=['POST'])
# def process_audio():
#     # Get the audio file from the request
#     audio_file = request.files['audio']  # Replace 'audio' with the name of your file input

#     # Read the audio file
#     waveform, sample_rate = librosa.load(audio_file, sr=16000)  # Load the audio file directly from the uploaded file
#     waveform = librosa.util.normalize(waveform)  # Normalize the waveform
#     embeddings = speaker_model.encode_batch(torch.tensor([waveform]))  # Get embeddings
#     speaker_embeddings = embeddings.squeeze(0).tolist()  # Convert to list for JSON serialization

#     return jsonify(speaker_embeddings=speaker_embeddings)  # Return the embeddings as JSON

@app.route('/api/people', methods=['GET'])
def get_people():
    # Fetch data and include the _id field as a string
    people = list(db.people.find({}))
    
    # Convert the documents into a JSON-friendly format
    for person in people:
        person['_id'] = str(person['_id'])  # Convert ObjectId to string
    
    return jsonify(people)  # Return the data as JSON


# Route for the chat page
@app.route('/chat')
def chat():
    person_id = request.args.get('id')  # Get the ID from the query parameter
    return render_template('chat.html', person_id=person_id)  # Pass ID to the chat template


@app.route('/api/people/<id>', methods=['GET'])
def get_person(id):
    person = db.people.find_one({"_id": ObjectId(id)})  # Adjust the query based on your database structure
    if person:
        return jsonify({"name": person['name'], "id": str(person['_id'])})
    return jsonify({"error": "Person not found"}), 404



@app.route("/api/get_messages/<person_name>", methods=["GET"])
def get_messages(person_name):
    global message_history
    message_history = ""

    # Fetch all messages from the "messages" collection for the given personName
    messages = list(db.messages.find({'personName': person_name}, {'_id': 0}))  # Exclude _id from the result

    # Append each message to the message_history in the desired format
    for message in messages:
        message_history += f"\nUser: {message['user']}\nAI: {message['ai']}"

    return jsonify(messages), 200



@app.route("/send_message", methods=["POST"])
def send_message():
    global message_history
    data = request.get_json()
    user_message = data.get('message')
    person_name = data.get('name')
    
    # Fetch the speaker embeddings from the database
    person = db.people.find_one({'name': person_name})
    if not person or 'speaker_embeddings' not in person:
        return jsonify({"error": "Speaker embeddings not found for this person."}), 404

    # Convert the embeddings back to a tensor if they were stored as a list
    speaker_embeddings = torch.tensor(person['speaker_embeddings'])
    description = person['description']

    # Generate AI response
    result = chain.invoke({"message_history": message_history, "description": description, "user_input": user_message})
    message_history += f"\nUser: {user_message}\nAI: {result}"

    # Store the message in the "messages" collection
    message_data = {
        'personName': person_name,
        'user': user_message,
        'ai': result
    }
    db.messages.insert_one(message_data)

    # Convert AI text response to speech using cloned voice
    inputs = processor(text=result, return_tensors="pt")
    speech = tts_model.generate_speech(inputs.input_ids, speaker_embeddings=speaker_embeddings, vocoder=vocoder)
    
    # Save the speech to a file
    output_file = "output_cloned_voice.wav"
    sf.write(output_file, speech.numpy(), 16000)
    
    # Return both the text response and the audio file URL
    return jsonify({"response": result, "audio_url": "/get_audio"})


# Route to render the add page
@app.route('/add', methods=['GET', 'POST'])
def add_person():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        audio_file = request.files['audio']

        if audio_file:
            # Load the audio file directly from the file stream
            waveform, sample_rate = librosa.load(audio_file, sr=16000)  # Load audio directly from the uploaded file
            waveform = librosa.util.normalize(waveform)  # Normalize the waveform
            
            # Load the speaker model
            speaker_model = EncoderClassifier.from_hparams(source="speechbrain/spkrec-xvect-voxceleb", run_opts={"device": "cpu"})
            
            # Get embeddings
            embeddings = speaker_model.encode_batch(torch.tensor([waveform]))  # Get embeddings
            speaker_embeddings = embeddings.squeeze(0).tolist()  # Convert to list for JSON serialization

            # Create a new person document with embeddings
            db.people.insert_one({
                'name': name,
                'description': description,
                'speaker_embeddings': speaker_embeddings  # Save embeddings
            })

            return jsonify({"message": "Person added successfully!"}), 201

    return render_template('add.html')

@app.route("/get_audio")
def get_audio():
    return send_file("output_cloned_voice.wav", as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
