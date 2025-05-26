/**
 * Main application logic for the Lorcana Card Recognition app
 */
const app = {
    // State
    isInitialized: false,
    isAutoCapturing: false,
    autoCaptureInterval: null,
    lastValidWarpedImage: null,

    // Initialize the application
    async init() {
        try {
            utils.log('Initializing application...');

            // Load configuration from server
            await config.loadFromServer();

            // Initialize UI
            ui.init();

            // Initialize camera
            const cameraInitialized = await camera.init();
            if (!cameraInitialized) {
                ui.showError('Failed to initialize camera. Please check permissions and try again.');
                return false;
            }

            this.isInitialized = true;
            utils.log('Application initialized successfully');
            return true;
        } catch (error) {
            utils.log('Initialization error:', error, 'error');
            ui.showError(`Failed to initialize: ${error.message}`);
            return false;
        }
    },

    // Capture frame and send to server for processing
    async captureAndProcess() {
        // Check if camera is ready before capturing and processing
        if (!this.isInitialized || !camera.isCameraReady()) {
            ui.showError('Camera not ready. Please refresh the page.');
            return;
        }

        try {
            // Capture frame
            const imageData = camera.captureFrame();

            // Get parameters from UI
            const params = ui.getParams();

            // Send to server
            const response = await api.processFrame(imageData, params);

            // Update UI with response
            ui.updateWithServerResponse(response);
        } catch (error) {
            utils.log('Processing error:', error, 'error');
            ui.showError(`Processing error: ${error.message}`);
        }
    },

    // Toggle automatic capture
    toggleAutoCapture() {
        this.isAutoCapturing = !this.isAutoCapturing;

        if (this.isAutoCapturing) {
            // Start auto capture
            this.autoCaptureInterval = setInterval(() => {
                // Check if camera is ready before capturing and processing
                if (camera.isCameraReady()) {
                    this.captureAndProcess();
                } else {
                    utils.log('Auto capture skipped: Camera not ready', 'warn');
                }
            }, config.processing.captureInterval);

            ui.elements.toggleAutoBtn.textContent = 'Auto: ON';
            ui.showSuccess('Auto capture enabled');
        } else {
            // Stop auto capture
            clearInterval(this.autoCaptureInterval);
            this.autoCaptureInterval = null;

            ui.elements.toggleAutoBtn.textContent = 'Auto: OFF';
            ui.showSuccess('Auto capture disabled');
        }
    }
};

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    await app.init();
});

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        // Page is visible again, restart camera if needed
        if (app.isInitialized && !camera.isActive()) {
            camera.init();
        }
    } else {
        // Page is hidden, stop auto capture to save resources
        if (app.isAutoCapturing) {
            clearInterval(app.autoCaptureInterval);
            app.autoCaptureInterval = null;
        }
    }
});