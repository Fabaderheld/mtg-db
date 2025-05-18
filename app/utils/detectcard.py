import cv2
import numpy as np
import requests
from PIL import Image
import io
import pytesseract
from difflib import SequenceMatcher
import json
import os
from concurrent.futures import ThreadPoolExecutor

class MTGCardIdentifier:
    def __init__(self):
        self.card_cache = {}
        self.cache_dir = "card_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    def download_card_image(self, url, card_name):
        """Download and cache card image"""
        cache_path = os.path.join(self.cache_dir, f"{card_name}.jpg")

        if os.path.exists(cache_path):
            return cv2.imread(cache_path)

        response = requests.get(url)
        image = Image.open(io.BytesIO(response.content))
        image.save(cache_path)
        return cv2.imread(cache_path)

    def match_image(self, input_image, reference_image):
        """Compare two images and return similarity score"""
        # Resize images to same size
        height = 400
        input_image = cv2.resize(input_image, (int(height * input_image.shape[1] / input_image.shape[0]), height))
        reference_image = cv2.resize(reference_image, (int(height * reference_image.shape[1] / reference_image.shape[0]), height))

        # Convert to grayscale
        input_gray = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
        reference_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)

        # Calculate SSIM
        try:
            from skimage.metrics import structural_similarity as ssim
            score = ssim(input_gray, reference_gray)
        except:
            # Fallback to histogram comparison if SSIM fails
            score = cv2.compareHist(
                cv2.calcHist([input_gray], [0], None, [256], [0, 256]),
                cv2.calcHist([reference_gray], [0], None, [256], [0, 256]),
                cv2.HISTCMP_CORREL
            )

        return score

    def identify_card(self, image_path):
        """Identify an MTG card using both OCR and image matching"""
        # Read input image
        input_image = cv2.imread(image_path)
        if input_image is None:
            return "Error: Could not read image"

        # Extract card name using OCR
        card_name = extract_card_name(input_image)

        # Get card data from Scryfall
        try:
            response = requests.get(f"https://api.scryfall.com/cards/search?q={card_name}")
            possible_matches = response.json()['data'][:5]  # Get top 5 possible matches
        except Exception as e:
            return f"Error fetching card data: {str(e)}"

        # Compare input image with possible matches
        best_match = None
        best_score = 0

        for card in possible_matches:
            if 'image_uris' not in card:
                continue

            reference_image = self.download_card_image(card['image_uris']['normal'], card['name'])
            score = self.match_image(input_image, reference_image)

            if score > best_score:
                best_score = score
                best_match = card

        if best_score > 0.5:  # Threshold for a good match
            return {
                'name': best_match['name'],
                'set': best_match['set_name'],
                'rarity': best_match['rarity'],
                'image_url': best_match['image_uris']['normal'],
                'price': best_match['prices']['usd'] if 'prices' in best_match else None,
                'confidence': best_score
            }
        else:
            return "Card not recognized with sufficient confidence"

def main():
    identifier = MTGCardIdentifier()
    image_path = 'path_to_your_card_image.jpg'  # Replace with your image path
    result = identifier.identify_card(image_path)

    if isinstance(result, dict):
        print(f"Card identified:")
        print(f"Name: {result['name']}")
        print(f"Set: {result['set']}")
        print(f"Rarity: {result['rarity']}")
        print(f"Price: ${result['price']}")
        print(f"Confidence: {result['confidence']*100:.2f}%")
        print(f"Image URL: {result['image_url']}")
    else:
        print(result)
