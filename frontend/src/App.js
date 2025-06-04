import React, { useState, useRef } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [extractedText, setExtractedText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [textEdits, setTextEdits] = useState([]);
  const [isEditMode, setIsEditMode] = useState(false);
  const [newText, setNewText] = useState("");
  const [fontSize, setFontSize] = useState(24);
  const [fontColor, setFontColor] = useState("#000000");
  const fileInputRef = useRef(null);
  const canvasRef = useRef(null);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setImagePreview(URL.createObjectURL(file));
      setExtractedText("");
      setOcrResult(null);
      setTextEdits([]);
      setIsEditMode(false);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const handleDrop = (event) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      setSelectedFile(file);
      setImagePreview(URL.createObjectURL(file));
      setExtractedText("");
      setOcrResult(null);
      setTextEdits([]);
      setIsEditMode(false);
    }
  };

  const handleUploadAndOCR = async () => {
    if (!selectedFile) return;

    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await axios.post(`${API}/upload-ocr`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setOcrResult(response.data);
      setExtractedText(response.data.extracted_text);
    } catch (error) {
      console.error('OCR extraction failed:', error);
      alert('Failed to extract text from image. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTextEdit = (newText) => {
    setExtractedText(newText);
  };

  const handleImageClick = (event) => {
    if (!isEditMode || !newText.trim()) return;

    const rect = event.target.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Calculate relative position based on actual image size
    const img = event.target;
    const scaleX = img.naturalWidth / img.width;
    const scaleY = img.naturalHeight / img.height;

    const actualX = Math.round(x * scaleX);
    const actualY = Math.round(y * scaleY);

    const newEdit = {
      text: newText,
      x: actualX,
      y: actualY,
      font_size: fontSize,
      font_color: fontColor
    };

    setTextEdits([...textEdits, newEdit]);
    setNewText("");
  };

  const downloadEditedImage = async () => {
    if (!ocrResult || textEdits.length === 0) {
      alert('No edits to save');
      return;
    }

    try {
      const editRequest = {
        file_id: ocrResult.id,
        edits: textEdits
      };

      const response = await axios.post(`${API}/edit-image`, editRequest, {
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `edited_${ocrResult.filename}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download edited image:', error);
      alert('Failed to download edited image. Please try again.');
    }
  };

  const clearEdits = () => {
    setTextEdits([]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-3xl font-bold text-gray-900">OCR Converter</h1>
              </div>
            </div>
            <div className="text-sm text-gray-500">
              Upload • Extract • Edit • Download
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Left Column - File Upload and Image */}
          <div className="space-y-6">
            {/* File Upload Area */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Image</h2>
              
              <div
                className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors cursor-pointer"
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="space-y-4">
                  <div className="flex justify-center">
                    <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 48 48">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-lg text-gray-600">Drop your image here or click to upload</p>
                    <p className="text-sm text-gray-500">Supports JPG, PNG, GIF, BMP formats</p>
                  </div>
                </div>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileSelect}
                className="hidden"
              />

              {selectedFile && (
                <div className="mt-4">
                  <p className="text-sm text-gray-600">Selected: {selectedFile.name}</p>
                  <button
                    onClick={handleUploadAndOCR}
                    disabled={isLoading}
                    className="mt-2 w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isLoading ? 'Extracting Text...' : 'Extract Text with OCR'}
                  </button>
                </div>
              )}
            </div>

            {/* Image Preview */}
            {imagePreview && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Image Preview</h3>
                <div className="relative">
                  <img
                    src={imagePreview}
                    alt="Preview"
                    className="w-full h-auto rounded-lg cursor-crosshair"
                    onClick={handleImageClick}
                  />
                  {isEditMode && (
                    <div className="absolute top-2 left-2 bg-yellow-100 border border-yellow-400 text-yellow-800 px-3 py-1 rounded text-sm">
                      Click on image to add text
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Text and Editing */}
          <div className="space-y-6">
            
            {/* Extracted Text */}
            {extractedText && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Extracted Text</h3>
                  {ocrResult && (
                    <span className="text-sm text-gray-500">
                      Confidence: {Math.round(ocrResult.confidence)}%
                    </span>
                  )}
                </div>
                <textarea
                  value={extractedText}
                  onChange={(e) => handleTextEdit(e.target.value)}
                  className="w-full h-40 p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="Extracted text will appear here..."
                />
              </div>
            )}

            {/* Text Editing Tools */}
            {ocrResult && (
              <div className="bg-white rounded-lg shadow-md p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Add New Text</h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      New Text
                    </label>
                    <input
                      type="text"
                      value={newText}
                      onChange={(e) => setNewText(e.target.value)}
                      className="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      placeholder="Enter text to add to image..."
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Font Size
                      </label>
                      <input
                        type="range"
                        min="12"
                        max="72"
                        value={fontSize}
                        onChange={(e) => setFontSize(parseInt(e.target.value))}
                        className="w-full"
                      />
                      <span className="text-sm text-gray-500">{fontSize}px</span>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Font Color
                      </label>
                      <input
                        type="color"
                        value={fontColor}
                        onChange={(e) => setFontColor(e.target.value)}
                        className="w-full h-8 border border-gray-300 rounded-md"
                      />
                    </div>
                  </div>

                  <div className="flex space-x-2">
                    <button
                      onClick={() => setIsEditMode(!isEditMode)}
                      className={`flex-1 py-2 px-4 rounded-md transition-colors ${
                        isEditMode
                          ? 'bg-green-600 text-white hover:bg-green-700'
                          : 'bg-gray-600 text-white hover:bg-gray-700'
                      }`}
                    >
                      {isEditMode ? 'Exit Edit Mode' : 'Enter Edit Mode'}
                    </button>
                    
                    {textEdits.length > 0 && (
                      <button
                        onClick={clearEdits}
                        className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                      >
                        Clear Edits
                      </button>
                    )}
                  </div>

                  {textEdits.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Text Edits ({textEdits.length})</h4>
                      <div className="space-y-2 max-h-32 overflow-y-auto">
                        {textEdits.map((edit, index) => (
                          <div key={index} className="text-sm bg-gray-50 p-2 rounded">
                            <span className="font-medium">"{edit.text}"</span>
                            <span className="text-gray-500"> at ({edit.x}, {edit.y})</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {textEdits.length > 0 && (
                    <button
                      onClick={downloadEditedImage}
                      className="w-full bg-indigo-600 text-white py-3 px-4 rounded-md hover:bg-indigo-700 transition-colors font-medium"
                    >
                      Download Edited Image
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;