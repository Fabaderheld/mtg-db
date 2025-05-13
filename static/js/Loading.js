function showLoading() {
    document.getElementById('loading-spinner').classList.add('show');
}

function hideLoading() {
    document.getElementById('loading-spinner').classList.remove('show');
}

// Optional: Hide it automatically on page load (if it's still visible for any reason)
window.addEventListener('load', () => hideLoading());

function showLoading() {
    document.getElementById('loading-spinner').classList.add('show');
}

function hideLoading() {
    document.getElementById('loading-spinner').classList.remove('show');
}

window.addEventListener('load', () => hideLoading());