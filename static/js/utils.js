/**
 * Utility functions for the Lorcana Card Recognition app
 */
const utils = {
    /**
     * Creates a debounced function that delays invoking func until after wait milliseconds
     * @param {Function} func - The function to debounce
     * @param {number} wait - The number of milliseconds to delay
     * @returns {Function} - The debounced function
     */
    debounce(func, wait) {
        let timeout;
        return function(...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    },

    /**
     * Creates a throttled function that only invokes func at most once per every wait milliseconds
     * @param {Function} func - The function to throttle
     * @param {number} wait - The number of milliseconds to wait between invocations
     * @returns {Function} - The throttled function
     */
    throttle(func, wait) {
        let lastCall = 0;
        return function(...args) {
            const now = Date.now();
            if (now - lastCall < wait) return;
            lastCall = now;
            return func.apply(this, args);
        };
    },

    /**
     * Logs messages to console if debug is enabled
     * @param {string} message - The message to log
     * @param {*} data - Optional data to log
     * @param {string} type - Log type (log, warn, error)
     */
    log(message, data = null, type = 'log') {
        if (!config.debug.enabled) return;

        if (data) {
            console[type](message, data);
        } else {
            console[type](message);
        }
    },

    /**
     * Formats a date object to a readable string
     * @param {Date} date - The date to format
     * @returns {string} - Formatted date string
     */
    formatDate(date) {
        return date.toLocaleString();
    },

    /**
     * Generates a unique ID
     * @returns {string} - A unique ID
     */
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },

    /**
     * Retries a function multiple times if it fails
     * @param {Function} fn - Async function to retry
     * @param {number} maxRetries - Maximum number of retries
     * @param {number} delay - Delay between retries in ms
     * @returns {Promise} - Result of the function
     */
    async retry(fn, maxRetries = config.processing.maxRetries, delay = config.processing.retryDelay) {
        let lastError;

        for (let i = 0; i < maxRetries; i++) {
            try {
                return await fn();
            } catch (error) {
                lastError = error;
                utils.log(`Retry ${i+1}/${maxRetries} failed:`, error, 'warn');

                if (i < maxRetries - 1) {
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
            }
        }

        throw lastError;
    }
};