import os
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import fitz
import numpy as np
import shutil

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Function to find points in PDF
def find_points_in_pdf(pdf_path):
    points = {}
    with fitz.open(pdf_path) as pdf_document:
        for page in pdf_document:
            for text_to_search in ['A', 'B', 'X']:
                text_instances = page.search_for(text_to_search)
                if text_instances:
                    points[text_to_search] = text_instances[0][:2]
    return points

# Function to calculate Bezier curve
def calculate_bezier_curve(point1, point2, control_point1, control_point2, num_points=100):
    t = np.linspace(0, 1, num_points)
    
    x_bezier = (1 - t)**3 * point1[0] + 3 * (1 - t)**2 * t * control_point1[0] + 3 * (1 - t) * t**2 * control_point2[0] + t**3 * point2[0]
    y_bezier = (1 - t)**3 * point1[1] + 3 * (1 - t)**2 * t * control_point1[1] + 3 * (1 - t) * t**2 * control_point2[1] + t**3 * point2[1]
    
    return x_bezier, y_bezier

# Function to calculate control points
def calculate_control_points(point_a, point_b, avoid_point, min_distance=60):
    x0, y0 = point_a
    x1, y1 = point_b
    x_avoid, y_avoid = avoid_point
    
    mid_x = (x0 + x1) / 2
    mid_y = (y0 + y1) / 2
    
    dir_x, dir_y = x_avoid - mid_x, y_avoid - mid_y
    
    length = np.sqrt(dir_x**2 + dir_y**2)
    dir_x /= length
    dir_y /= length
    
    offset = 60
    control_x = mid_x + dir_x * offset
    control_y = mid_y + dir_y * offset
    
    return (control_x, control_y), (control_x, control_y)

# Function to draw curve on PDF
def draw_curve_on_pdf(pdf_path, point_a, point_b, avoid_point):
    pdf_document = fitz.open(pdf_path)
    page = pdf_document[0]
    
    control_point1, control_point2 = calculate_control_points(point_a, point_b, avoid_point)

    x_curve, y_curve = calculate_bezier_curve(point_a, point_b, control_point1, control_point2)

    for i in range(len(x_curve) - 1):
        page.draw_line((x_curve[i], y_curve[i]), (x_curve[i + 1], y_curve[i + 1]), color=(1, 0, 0), width=2)
    
    temp_pdf_path = pdf_path + '_temp'
    pdf_document.save(temp_pdf_path)
    pdf_document.close()
    
    return temp_pdf_path

# Function to process PDF file
def process_pdf(pdf_path):
    points = find_points_in_pdf(pdf_path)

    if 'A' in points and 'B' in points and 'X' in points:
        point_a = points['A']
        point_b = points['B']
        avoid_point = points['X']
        
        processed_pdf_path = draw_curve_on_pdf(pdf_path, point_a, point_b, avoid_point)
        
        return processed_pdf_path
    else:
        return None

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(pdf_path)

        try:
            # Process the PDF file
            processed_pdf_path = process_pdf(pdf_path)

            if processed_pdf_path:
                return send_file(processed_pdf_path, as_attachment=True, download_name='modified.pdf')
            else:
                return jsonify({'error': 'Points A, B, and/or X not found in the PDF.'}), 400

        except Exception as e:
            print(f"Error processing PDF: {e}")
            return jsonify({'error': 'Processing failed'}), 500

    return jsonify({'error': 'Upload failed'}), 500

if __name__ == '__main__':
    app.run(debug=True)
