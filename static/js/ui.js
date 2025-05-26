/**
 * UI management for the Lorcana Card Recognition app
 */
const ui = {
    elements: {
        // Status elements
        errorContainer: document.getElementById('error-container'),
        successContainer: document.getElementById('success-container'),
        loadingContainer: document.getElementById('loading-container'),

        // Camera elements
        videoContainer: document.querySelector('.video-container'),
        video: document.getElementById('camera-feed'),
        processedFrame: document.getElementById('processed-frame'),
        captureBtn: document.getElementById('capture-btn'),
        toggleCameraBtn: document.getElementById('toggle-camera-btn'),
        toggleAutoBtn: document.getElementById('toggle-auto-btn'),

        // Results elements
        warpedCardImage: document.getElementById('warped-card-image'),
        nameRegion: document.getElementById('name-region'),
        numberRegion: document.getElementById('number-region'),
        extractedTextName: document.getElementById('extracted-text-name'),
        extractedTextCardNumber: document.getElementById('extracted-text-card-number'),
        infoContent: document.getElementById('info-content'),

        // Settings elements
        toggleSettings: document.getElementById('toggle-settings'),
        settingsPanel: document.getElementById('settings-panel'),

        // Parameter sliders
        minAreaSlider: document.getElementById('min-area'),
        minAreaValue: document.getElementById('min-area-value'),
        cannyLowSlider: document.getElementById('canny-low'),
        cannyLowValue: document.getElementById('canny-low-value'),
        cannyHighSlider: document.getElementById('canny-high'),
        cannyHighValue: document.getElementById('canny-high-value'),
        epsilonSlider: document.getElementById('epsilon'),
        epsilonValue: document.getElementById('epsilon-value'),

        // OCR region sliders
        ocrXStartNameSlider: document.getElementById('ocr-x-start-name'),
        ocrXStartNameValue: document.getElementById('ocr-x-start-name-value'),
        ocrXEndNameSlider: document.getElementById('ocr-x-end-name'),
        ocrXEndNameValue: document.getElementById('ocr-x-end-name-value'),
        ocrYStartNameSlider: document.getElementById('ocr-y-start-name'),
        ocrYStartNameValue: document.getElementById('ocr-y-start-name-value'),
        ocrYEndNameSlider: document.getElementById('ocr-y-end-name'),
        ocrYEndNameValue: document.getElementById('ocr-y-end-name-value'),

        ocrXStartCardNumberSlider: document.getElementById('ocr-x-start-card-number'),
        ocrXStartCardNumberValue: document.getElementById('ocr-x-start-card-number-value'),
        ocrXEndCardNumberSlider: document.getElementById('ocr-x-end-card-number'),
        ocrXEndCardNumberValue: document.getElementById('ocr-x-end-card-number-value'),
        ocrYStartCardNumberSlider: document.getElementById('ocr-y-start-card-number'),
        ocrYStartCardNumberValue: document.getElementById('ocr-y-start-card-number-value'),
        ocrYEndCardNumberSlider: document.getElementById('ocr-y-end-card-number'),
        ocrYEndCardNumberValue: document.getElementById('ocr-y-end-card-number-value'),

        // Debug checkboxes
        debugCheckboxes: document.querySelectorAll('.debug-controls input[type="checkbox"]'),

        // Debug images
        debugImages: {
            edges: document.getElementById('edges-img'),
            processedEdges: document.getElementById('processed-edges-img'),
            allContours: document.getElementById('all-contours-img'),
            warped: document.getElementById('warped-img'),
            nameRegionName: document.getElementById('name-region-img-name'),
            nameRegionCardNumber: document.getElementById('name-region-img-card-number'),
            thresholdName: document.getElementById('threshold-img-name'),
            thresholdCardNumber: document.getElementById('threshold-img-card-number')
        }
    },

    // Initialize UI
    init() {
        this.setupEventListeners();
        this.setDefaultValues();
        this.updateOcrRegions();
    },

    // Set up event listeners
    setupEventListeners() {
        // Settings toggle
        this.elements.toggleSettings.addEventListener('click', () => {
            const panel = this.elements.settingsPanel;
            if (panel.style.display === 'block') {
                panel.style.display = 'none';
                this.elements.toggleSettings.textContent = 'Show Advanced Settings';
            } else {
                panel.style.display = 'block';
                this.elements.toggleSettings.textContent = 'Hide Advanced Settings';
            }
        });

        // Camera controls
        this.elements.captureBtn.addEventListener('click', () => app.captureAndProcess());
        this.elements.toggleCameraBtn.addEventListener('click', () => camera.toggleCamera());
        this.elements.toggleAutoBtn.addEventListener('click', () => app.toggleAutoCapture());

        // Parameter sliders
        this.setupSlider(this.elements.minAreaSlider, this.elements.minAreaValue);
        this.setupSlider(this.elements.cannyLowSlider, this.elements.cannyLowValue);
        this.setupSlider(this.elements.cannyHighSlider, this.elements.cannyHighValue);

        // Epsilon slider (special case for decimal display)
        this.elements.epsilonSlider.addEventListener('input', () => {
            const value = parseInt(this.elements.epsilonSlider.value) / 100;
            this.elements.epsilonValue.textContent = value.toFixed(2);
            this.updateOcrRegions();
        });

        // OCR region sliders
        const ocrSliders = [
            this.elements.ocrXStartNameSlider, this.elements.ocrXEndNameSlider,
            this.elements.ocrYStartNameSlider, this.elements.ocrYEndNameSlider,
            this.elements.ocrXStartCardNumberSlider, this.elements.ocrXEndCardNumberSlider,
            this.elements.ocrYStartCardNumberSlider, this.elements.ocrYEndCardNumberSlider
        ];

        const ocrValues = [
            this.elements.ocrXStartNameValue, this.elements.ocrXEndNameValue,
            this.elements.ocrYStartNameValue, this.elements.ocrYEndNameValue,
            this.elements.ocrXStartCardNumberValue, this.elements.ocrXEndCardNumberValue,
            this.elements.ocrYStartCardNumberValue, this.elements.ocrYEndCardNumberValue
        ];

        for (let i = 0; i < ocrSliders.length; i++) {
            this.setupSlider(ocrSliders[i], ocrValues[i], this.updateOcrRegions.bind(this));
        }

        // Debug checkboxes
        this.elements.debugCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => this.updateDebugImageVisibility());
        });

        // Update OCR regions when warped image loads
        this.elements.warpedCardImage.addEventListener('load', () => {
            this.updateOcrRegionSliderLimits();
            this.updateOcrRegions();
        });

        // Window resize event
        window.addEventListener('resize', utils.debounce(() => {
            this.updateOcrRegions();
        }, 200));
    },

    // Set up a slider with its value display
    setupSlider(slider, valueDisplay, callback) {
        slider.addEventListener('input', () => {
            valueDisplay.textContent = slider.value;
            if (callback) callback();
        });
    },

    // Set default values from config
    setDefaultValues() {
        // Detection parameters
        this.elements.minAreaSlider.value = config.defaults.minArea;
        this.elements.minAreaValue.textContent = config.defaults.minArea;

        this.elements.cannyLowSlider.value = config.defaults.cannyLow;
        this.elements.cannyLowValue.textContent = config.defaults.cannyLow;

        this.elements.cannyHighSlider.value = config.defaults.cannyHigh;
        this.elements.cannyHighValue.textContent = config.defaults.cannyHigh;

        this.elements.epsilonSlider.value = config.defaults.epsilon * 100;
        this.elements.epsilonValue.textContent = config.defaults.epsilon.toFixed(2);

        // OCR regions - Name
        this.elements.ocrXStartNameSlider.value = config.defaults.ocrRegions.name.xStart;
        this.elements.ocrXStartNameValue.textContent = config.defaults.ocrRegions.name.xStart;

        this.elements.ocrXEndNameSlider.value = config.defaults.ocrRegions.name.xEnd;
        this.elements.ocrXEndNameValue.textContent = config.defaults.ocrRegions.name.xEnd;

        this.elements.ocrYStartNameSlider.value = config.defaults.ocrRegions.name.yStart;
        this.elements.ocrYStartNameValue.textContent = config.defaults.ocrRegions.name.yStart;

        this.elements.ocrYEndNameSlider.value = config.defaults.ocrRegions.name.yEnd;
        this.elements.ocrYEndNameValue.textContent = config.defaults.ocrRegions.name.yEnd;

        // OCR regions - Card Number
        this.elements.ocrXStartCardNumberSlider.value = config.defaults.ocrRegions.cardNumber.xStart;
        this.elements.ocrXStartCardNumberValue.textContent = config.defaults.ocrRegions.cardNumber.xStart;

        this.elements.ocrXEndCardNumberSlider.value = config.defaults.ocrRegions.cardNumber.xEnd;
        this.elements.ocrXEndCardNumberValue.textContent = config.defaults.ocrRegions.cardNumber.xEnd;

        this.elements.ocrYStartCardNumberSlider.value = config.defaults.ocrRegions.cardNumber.yStart;
        this.elements.ocrYStartCardNumberValue.textContent = config.defaults.ocrRegions.cardNumber.yStart;

        this.elements.ocrYEndCardNumberSlider.value = config.defaults.ocrRegions.cardNumber.yEnd;
        this.elements.ocrYEndCardNumberValue.textContent = config.defaults.ocrRegions.cardNumber.yEnd;
    },

    // Update OCR region slider limits based on warped image dimensions
    updateOcrRegionSliderLimits() {
        const img = this.elements.warpedCardImage;

        if (img.style.display !== 'none' && img.naturalWidth > 0) {
            const imgWidth = img.naturalWidth;
            const imgHeight = img.naturalHeight;

            // Update X sliders
            [
                this.elements.ocrXStartNameSlider,
                this.elements.ocrXEndNameSlider,
                this.elements.ocrXStartCardNumberSlider,
                this.elements.ocrXEndCardNumberSlider
            ].forEach(slider => {
                slider.max = imgWidth;
                if (parseInt(slider.value) > imgWidth) {
                    slider.value = imgWidth;
                    document.getElementById(slider.id + '-value').textContent = imgWidth;
                }
            });

            // Update Y sliders
            [
                this.elements.ocrYStartNameSlider,
                this.elements.ocrYEndNameSlider,
                this.elements.ocrYStartCardNumberSlider,
                this.elements.ocrYEndCardNumberSlider
            ].forEach(slider => {
                slider.max = imgHeight;
                if (parseInt(slider.value) > imgHeight) {
                    slider.value = imgHeight;
                    document.getElementById(slider.id + '-value').textContent = imgHeight;
                }
            });
        }
    },

    // Update OCR region visual indicators
    updateOcrRegions() {
        const img = this.elements.warpedCardImage;

        if (img.style.display !== 'none' && img.naturalWidth > 0) {
            // Get values from sliders
            const nameRegion = {
                xStart: parseInt(this.elements.ocrXStartNameSlider.value),
                xEnd: parseInt(this.elements.ocrXEndNameSlider.value),
                yStart: parseInt(this.elements.ocrYStartNameSlider.value),
                yEnd: parseInt(this.elements.ocrYEndNameSlider.value)
            };

            const numberRegion = {
                xStart: parseInt(this.elements.ocrXStartCardNumberSlider.value),
                xEnd: parseInt(this.elements.ocrXEndCardNumberSlider.value),
                yStart: parseInt(this.elements.ocrYStartCardNumberSlider.value),
                yEnd: parseInt(this.elements.ocrYEndCardNumberSlider.value)
            };

            // Calculate scaling factor
            const scaleX = img.clientWidth / img.naturalWidth;
            const scaleY = img.clientHeight / img.naturalHeight;

            // Update name region
            this.elements.nameRegion.style.display = 'block';
            this.elements.nameRegion.style.left = `${Math.min(nameRegion.xStart, nameRegion.xEnd) * scaleX}px`;
            this.elements.nameRegion.style.top = `${Math.min(nameRegion.yStart, nameRegion.yEnd) * scaleY}px`;
            this.elements.nameRegion.style.width = `${Math.abs(nameRegion.xEnd - nameRegion.xStart) * scaleX}px`;
            this.elements.nameRegion.style.height = `${Math.abs(nameRegion.yEnd - nameRegion.yStart) * scaleY}px`;

            // Update number region
            this.elements.numberRegion.style.display = 'block';
            this.elements.numberRegion.style.left = `${Math.min(numberRegion.xStart, numberRegion.xEnd) * scaleX}px`;
            this.elements.numberRegion.style.top = `${Math.min(numberRegion.yStart, numberRegion.yEnd) * scaleY}px`;
            this.elements.numberRegion.style.width = `${Math.abs(numberRegion.xEnd - numberRegion.xStart) * scaleX}px`;
            this.elements.numberRegion.style.height = `${Math.abs(numberRegion.yEnd - numberRegion.yStart) * scaleY}px`;
        } else {
            // Hide regions if no image
            this.elements.nameRegion.style.display = 'none';
            this.elements.numberRegion.style.display = 'none';
        }
    },

    // Get current parameter values
    getParams() {
        return {
            min_area: parseInt(this.elements.minAreaSlider.value),
            canny_low: parseInt(this.elements.cannyLowSlider.value),
            canny_high: parseInt(this.elements.cannyHighSlider.value),
            epsilon: parseInt(this.elements.epsilonSlider.value) / 100,
            ocr_x_start_name: parseInt(this.elements.ocrXStartNameSlider.value),
            ocr_x_end_name: parseInt(this.elements.ocrXEndNameSlider.value),
            ocr_y_start_name: parseInt(this.elements.ocrYStartNameSlider.value),
            ocr_y_end_name: parseInt(this.elements.ocrYEndNameSlider.value),
            ocr_x_start_card_number: parseInt(this.elements.ocrXStartCardNumberSlider.value),
            ocr_x_end_card_number: parseInt(this.elements.ocrXEndCardNumberSlider.value),
            ocr_y_start_card_number: parseInt(this.elements.ocrYStartCardNumberSlider.value),
            ocr_y_end_card_number: parseInt(this.elements.ocrYEndCardNumberSlider.value)
        };
    },

    // Show error message
    showError(message, duration = 5000) {
        this.elements.errorContainer.textContent = message;
        this.elements.errorContainer.style.display = 'block';
        this.elements.successContainer.style.display = 'none';

        if (duration > 0) {
            setTimeout(() => {
                this.elements.errorContainer.style.display = 'none';
            }, duration);
        }
    },

    // Show success message
    showSuccess(message, duration = 3000) {
        this.elements.successContainer.textContent = message;
        this.elements.successContainer.style.display = 'block';
        this.elements.errorContainer.style.display = 'none';

        if (duration > 0) {
            setTimeout(() => {
                this.elements.successContainer.style.display = 'none';
            }, duration);
        }
    },

    // Show loading indicator
    showLoading() {
        this.elements.loadingContainer.style.display = 'flex';
    },

    // Hide loading indicator
    hideLoading() {
        this.elements.loadingContainer.style.display = 'none';
    },

    // Update UI with server response data
    updateWithServerResponse(data) {
        // Update processed frame
        if (data.processed_image) {
            this.elements.processedFrame.src = data.processed_image;
            this.elements.processedFrame.style.display = 'block';
            this.elements.video.style.display = 'none';
        } else {
            this.elements.processedFrame.style.display = 'none';
            this.elements.video.style.display = 'block';
        }

        // Update warped card image
        if (data.warped_image) {
            this.elements.warpedCardImage.src = data.warped_image;
            this.elements.warpedCardImage.style.display = 'block';
            app.lastValidWarpedImage = data.warped_image;
        } else if (app.lastValidWarpedImage) {
            // Keep showing the last valid image
        } else {
            this.elements.warpedCardImage.style.display = 'none';
        }

        // Update extracted text
        if (data.extracted_text_name) {
            this.elements.extractedTextName.textContent = 'Extracted Name: ' + data.extracted_text_name;
        } else {
            this.elements.extractedTextName.textContent = 'No name extracted';
        }

        if (data.extracted_text_card_number) {
            this.elements.extractedTextCardNumber.textContent = 'Extracted Card Number: ' + data.extracted_text_card_number;
        } else {
            this.elements.extractedTextCardNumber.textContent = 'No card number extracted';
        }

        // Update card info
        let cardHtml = '';
        if (data.card_info && data.card_info.name) {
            cardHtml = `
                <div class="card-details">
                    <div class="card-detail"><strong>Name:</strong> ${data.card_info.name}</div>
                    <div class="card-detail"><strong>Set:</strong> ${data.card_info.set || 'Unknown'}</div>
                    <div class="card-detail"><strong>Type:</strong> ${data.card_info.type || 'Unknown'}</div>
                    <div class="card-detail"><strong>Ink:</strong> ${data.card_info.ink || 'Unknown'}</div>
                    <div class="card-detail"><strong>Cost:</strong> ${data.card_info.cost || 'Unknown'}</div>
                    <div class="card-detail"><strong>Strength:</strong> ${data.card_info.strength || 'Unknown'}</div>
                    <div class="card-detail"><strong>Willpower:</strong> ${data.card_info.willpower || 'Unknown'}</div>
                    <div class="card-detail"><strong>Rarity:</strong> ${data.card_info.rarity || 'Unknown'}</div>
                    <div class="card-detail"><strong>Text:</strong> ${data.card_info.text || 'Unknown'}</div>
                </div>
            `;

            // Show success message when card is identified
            this.showSuccess(`Card identified: ${data.card_info.name}`);
        } else {
            cardHtml = '<div class="no-card">No card detected</div>';
        }

        this.elements.infoContent.innerHTML = cardHtml;

        // Update debug images
        if (data.debug_images) {
            const imageMapping = {
                'edges': this.elements.debugImages.edges,
                'processed_edges': this.elements.debugImages.processedEdges,
                'all_contours': this.elements.debugImages.allContours,
                'warped': this.elements.debugImages.warped,
                'name_region_img_name': this.elements.debugImages.nameRegionName,
                'name_region_img_card_number': this.elements.debugImages.nameRegionCardNumber,
                'threshold_img_name': this.elements.debugImages.thresholdName,
                'threshold_img_card_number': this.elements.debugImages.thresholdCardNumber
            };

            // Update debug images
            for (const [key, value] of Object.entries(data.debug_images)) {
                if (imageMapping[key] && value) {
                    imageMapping[key].src = value;
                    imageMapping[key].style.display = 'block';
                }
            }

            this.updateDebugImageVisibility();
        }
    },

    // Update debug image visibility based on checkboxes
    updateDebugImageVisibility() {
        const checkboxMapping = {
            'show-edges': this.elements.debugImages.edges,
            'show-processed-edges': this.elements.debugImages.processedEdges,
            'show-all-contours': this.elements.debugImages.allContours,
            'show-warped': this.elements.debugImages.warped,
            'show-name-region-name': this.elements.debugImages.nameRegionName,
            'show-name-region-card-number': this.elements.debugImages.nameRegionCardNumber,
            'show-threshold-name': this.elements.debugImages.thresholdName,
            'show-threshold-card-number': this.elements.debugImages.thresholdCardNumber
        };

        for (const [checkboxId, imgElement] of Object.entries(checkboxMapping)) {
            const checkbox = document.getElementById(checkboxId);
            if (checkbox && imgElement) {
                imgElement.style.display = checkbox.checked ? 'block' : 'none';
            }
        }
    }
};