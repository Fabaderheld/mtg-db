/**
 * Configuration settings for the Lorcana Card Recognition app
 */
const config = {
    // API endpoints
    apiEndpoints: {
        processFrame: '/lorcana/process_frame',
        getOcrDefaults: '/lorcana/get_ocr_defaults'
    },

    // Default parameters
    defaults: {
        minArea: 10000,
        cannyLow: 50,
        cannyHigh: 150,
        epsilon: 0.15,
        ocrRegions: {
            name: {
                xStart: 40,
                xEnd: 380,
                yStart: 30,
                yEnd: 80
            },
            cardNumber: {
                xStart: 40,
                xEnd: 380,
                yStart: 500,
                yEnd: 550
            }
        }
    },

    // Processing settings
    processing: {
        captureInterval: 1000, // ms between automatic captures
        imageQuality: 0.8,     // JPEG quality (0-1)
        maxRetries: 3,         // API request retries
        retryDelay: 1000       // ms between retries
    },

    // Debug settings
    debug: {
        enabled: true,
        logApiRequests: true,
        logApiResponses: false // Set to false to avoid logging large image data
    },

    // Load configuration from server
    async loadFromServer() {
        try {
            const response = await fetch(this.apiEndpoints.getOcrDefaults);
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

            const data = await response.json();

            // Update OCR regions with server values
            if (data) {
                this.defaults.ocrRegions.name.xStart = data.ocr_x_start_name || this.defaults.ocrRegions.name.xStart;
                this.defaults.ocrRegions.name.xEnd = data.ocr_x_end_name || this.defaults.ocrRegions.name.xEnd;
                this.defaults.ocrRegions.name.yStart = data.ocr_y_start_name || this.defaults.ocrRegions.name.yStart;
                this.defaults.ocrRegions.name.yEnd = data.ocr_y_end_name || this.defaults.ocrRegions.name.yEnd;

                this.defaults.ocrRegions.cardNumber.xStart = data.ocr_x_start_card_number || this.defaults.ocrRegions.cardNumber.xStart;
                this.defaults.ocrRegions.cardNumber.xEnd = data.ocr_x_end_card_number || this.defaults.ocrRegions.cardNumber.xEnd;
                this.defaults.ocrRegions.cardNumber.yStart = data.ocr_y_start_card_number || this.defaults.ocrRegions.cardNumber.yStart;
                this.defaults.ocrRegions.cardNumber.yEnd = data.ocr_y_end_card_number || this.defaults.ocrRegions.cardNumber.yEnd;
            }

            return true;
        } catch (error) {
            console.warn('Failed to load server configuration:', error);
            return false;
        }
    }
};