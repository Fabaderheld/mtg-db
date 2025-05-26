/**
 * Camera handling for the Lorcana Card Recognition app
 */
const camera = {
    video: document.getElementById('camera-feed'),
    canvas: document.getElementById('canvas'),
    ctx: null,
    stream: null,
    facingMode: 'environment', // 'environment' for back camera, 'user' for front
    isReady: false, // Add a flag to track camera readiness

    // Initialize camera
    async init() {
        this.ctx = this.canvas.getContext('2d');

        try {
            await this.startCamera();
            this.isReady = true; // Set the flag to true when camera is ready
            return true;
        } catch (error) {
            ui.showError(`Camera error: ${error.message}`);
            this.isReady = false; // Ensure the flag is false on error
            return false;
        }
    },

    // Start camera with current facing mode
    async startCamera() {
        try {
            // Stop any existing stream
            if (this.stream) {
                this.stopCamera();
            }

            // Request camera access
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: this.facingMode,
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                }
            });

            // Set video source
            this.video.srcObject = this.stream;

            // Wait for video to be ready
            return new Promise((resolve) => {
                this.video.onloadedmetadata = () => {
                    // Set canvas dimensions to match video
                    this.canvas.width = this.video.videoWidth;
                    this.canvas.height = this.video.videoHeight;

                    // Show video
                    this.video.style.display = 'block';
                    document.getElementById('processed-frame').style.display = 'none';

                    utils.log(`Camera started: ${this.video.videoWidth}x${this.video.videoHeight}`);
                    resolve(true);
                };

                // Handle errors
                this.video.onerror = (error) => {
                    utils.log('Video error:', error, 'error');
                    resolve(false);
                };
            });
        } catch (error) {
            utils.log('Camera access error:', error, 'error');
            throw error;
        }
    },

    // Stop camera
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.video.srcObject = null;
            this.stream = null;
        }
    },

    // Toggle between front and back camera
    async toggleCamera() {
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        ui.showLoading();

        try {
            await this.startCamera();
            ui.showSuccess(`Switched to ${this.facingMode === 'environment' ? 'back' : 'front'} camera`);
        } catch (error) {
            ui.showError(`Failed to switch camera: ${error.message}`);
            // Revert to previous camera if switching fails
            this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
            await this.startCamera();
        } finally {
            ui.hideLoading();
        }
    },

    // Capture current frame
    captureFrame() {
        if (!this.stream) {
            throw new Error('Camera not initialized');
        }

        // Draw video frame to canvas
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        // Convert to data URL
        return this.canvas.toDataURL('image/jpeg', config.processing.imageQuality);
    },

    // Check if camera is active
    isActive() {
        return !!this.stream && this.stream.active;
    },

    // Check if camera is ready
    isCameraReady() {
        return this.isReady;
    }
};