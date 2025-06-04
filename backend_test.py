import requests
import os
import sys
import base64
from PIL import Image
import io
import time
from datetime import datetime

class OCRAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.file_id = None
        self.test_image_path = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        
        if not headers:
            headers = {}
            
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers)
                else:
                    response = requests.post(url, json=data, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                if response.headers.get('Content-Type', '').startswith('application/json'):
                    return success, response.json()
                return success, response
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")
                return False, None

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, None

    def create_test_image(self):
        """Create a simple test image with text for OCR testing"""
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a white image
        img = Image.new('RGB', (800, 400), color='white')
        d = ImageDraw.Draw(img)
        
        # Try to use a system font, or use default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        # Add text to the image
        d.text((50, 50), "Hello OCR Test", fill='black', font=font)
        d.text((50, 150), "Testing 123", fill='black', font=font)
        d.text((50, 250), "This is a sample image for OCR testing", fill='black', font=font)
        
        # Save the image to a temporary file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_image_path = f"/tmp/ocr_test_image_{timestamp}.png"
        img.save(test_image_path)
        
        self.test_image_path = test_image_path
        return test_image_path

    def test_health_check(self):
        """Test the health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api",
            200
        )
        if success:
            print(f"Response: {response}")
        return success

    def test_upload_ocr(self):
        """Test image upload and OCR extraction"""
        if not self.test_image_path:
            self.create_test_image()
            
        with open(self.test_image_path, 'rb') as img:
            files = {'file': ('test_image.png', img, 'image/png')}
            success, response = self.run_test(
                "Upload and OCR",
                "POST",
                "api/upload-ocr",
                200,
                files=files
            )
            
        if success:
            self.file_id = response.get('id')
            print(f"Extracted Text: {response.get('extracted_text')}")
            print(f"Confidence: {response.get('confidence')}%")
            print(f"File ID: {self.file_id}")
        return success

    def test_get_ocr_results(self):
        """Test retrieving OCR results"""
        success, response = self.run_test(
            "Get OCR Results",
            "GET",
            "api/ocr-results",
            200
        )
        if success:
            print(f"Found {len(response)} OCR results")
        return success

    def test_edit_image(self):
        """Test image editing functionality"""
        if not self.file_id:
            print("❌ No file ID available for editing. Run upload test first.")
            return False
            
        edit_data = {
            "file_id": self.file_id,
            "edits": [
                {
                    "text": "Added Text",
                    "x": 100,
                    "y": 300,
                    "font_size": 30,
                    "font_color": "#FF0000"
                }
            ]
        }
        
        success, response = self.run_test(
            "Edit Image",
            "POST",
            "api/edit-image",
            200,
            data=edit_data
        )
        
        if success:
            # Save the edited image for verification
            edited_image_path = f"/tmp/edited_image_{self.file_id}.png"
            with open(edited_image_path, 'wb') as f:
                f.write(response.content)
            print(f"Edited image saved to {edited_image_path}")
        return success

    def test_get_image(self):
        """Test retrieving an image by ID"""
        if not self.file_id:
            print("❌ No file ID available for retrieval. Run upload test first.")
            return False
            
        success, response = self.run_test(
            "Get Image",
            "GET",
            f"api/image/{self.file_id}",
            200
        )
        
        if success:
            # Save the retrieved image for verification
            retrieved_image_path = f"/tmp/retrieved_image_{self.file_id}.png"
            with open(retrieved_image_path, 'wb') as f:
                f.write(response.content)
            print(f"Retrieved image saved to {retrieved_image_path}")
        return success

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting OCR API Tests...")
        
        # Create test image
        self.create_test_image()
        print(f"Created test image at {self.test_image_path}")
        
        # Run tests
        self.test_health_check()
        self.test_upload_ocr()
        self.test_get_ocr_results()
        self.test_edit_image()
        self.test_get_image()
        
        # Print results
        print(f"\n📊 Tests passed: {self.tests_passed}/{self.tests_run}")
        return self.tests_passed == self.tests_run

def main():
    # Get backend URL from environment or use default
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', 'https://a6ce8e83-8966-4257-9ac1-cf079a563ebb.preview.emergentagent.com')
    
    # Run tests
    tester = OCRAPITester(backend_url)
    success = tester.run_all_tests()
    
    # Clean up test image
    if tester.test_image_path and os.path.exists(tester.test_image_path):
        os.remove(tester.test_image_path)
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
