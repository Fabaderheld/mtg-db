/**
 * API communication for the Lorcana Card Recognition app
 */
const api = {
    /**
     * Send a frame to the server for processing
     * @param {string} imageData - Base64 encoded image data
     * @param {Object} params - Processing parameters
     * @returns {Promise<Object>} - Server response
     */
    async processFrame(imageData, params) {
        ui.showLoading();

        try {
            // Log API request if debug enabled
            if (config.debug.logApiRequests) {
                utils.log('Sending frame to server with params:', params);
            }

            // Send request to server
            const response = await utils.retry(async () => {
                const res = await fetch(config.apiEndpoints.processFrame, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image: imageData,
                        ...params
                    })
                });

                if (!res.ok) {
                    throw new Error(`HTTP error! Status: ${res.status}`);
                }

                return res.json();
            });

            // Log API response if debug enabled
            if (config.debug.logApiResponses) {
                utils.log('Server response:', response);
            }

            return response;
        } catch (error) {
            utils.log('API error:', error, 'error');
            throw error;
        } finally {
            ui.hideLoading();
        }
    }
};