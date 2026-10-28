import os
import google.generativeai as genai
from flask import Blueprint, request, jsonify
from PIL import Image

main = Blueprint('main', __name__)

# Gemini AI কনফিগারেশন
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

@main.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Welcome to Study Mind AI API!"})

@main.route('/analyze', methods=['POST'])
def analyze_image():
    if 'file' not in request.files:
        return jsonify({"error": "কোন ফাইল আপলোড করা হয়নি"}), 400
    
    file = request.files['file']
    prompt = request.form.get('prompt', 'এই ছবিটির বিস্তারিত বর্ণনা দিন এবং মূল পয়েন্টগুলো বুঝিয়ে বলুন।')

    if file.filename == '':
        return jsonify({"error": "ফাইল সিলেক্ট করা হয়নি"}), 400

    if file:
        file_path = os.path.join(os.getcwd(), 'uploads', file.filename)
        file.save(file_path)

        try:
            # ইমেজ ওপেন ও Gemini AI তে পাঠানো
            image = Image.open(file_path)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([prompt, image])

            return jsonify({
                "status": "success",
                "filename": file.filename,
                "analysis": response.text
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500