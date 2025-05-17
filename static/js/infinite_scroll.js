let page = 1;
let loading = false;
let endOfCards = false;

function getFetchUrl() {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set('page', page + 1);
    console.log('Fetching URL:', currentUrl.toString());
    return currentUrl.toString();
}

function fetchMoreCards() {
    if (endOfCards || loading) {
        console.log('Skipping fetch - endOfCards:', endOfCards, 'loading:', loading);
        return;
    }

    loading = true;
    console.log('Fetching more cards - page:', page + 1);
    showLoading();

    fetch(getFetchUrl(), {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        console.log('Response status:', response.status);
        if (response.status === 204) {
            // No more cards
            endOfCards = true;
            throw new Error('No more cards');
        }
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.text();
    })
    .then(html => {
        console.log('Received HTML length:', html.length);
        const cardList = document.getElementById('card-list');
        if (!cardList) {
            console.error('Card list container not found!');
            return;
        }

        if (html.trim() === '') {
            endOfCards = true;
            cardList.insertAdjacentHTML('beforeend',
                '<div class="col-12 text-center mt-3 mb-3">' +
                '<p>No more cards to load</p></div>'
            );
        } else {
            cardList.insertAdjacentHTML('beforeend', html);
            page += 1;
            console.log('Updated page to:', page);
        }
    })
    .catch(error => {
        console.log('Fetch error or no more cards:', error.message);
        if (error.message !== 'No more cards') {
            const cardList = document.getElementById('card-list');
            if (cardList) {
                cardList.insertAdjacentHTML('beforeend',
                    '<div class="col-12 text-center mt-3 mb-3 text-danger">' +
                    '<p>Error loading more cards. Please try again later.</p></div>'
                );
            }
        }
    })
    .finally(() => {
        hideLoading();
        loading = false;
        console.log('Fetch complete - loading:', loading);
    });
}

// Improved scroll detection
function isNearBottom() {
    const scrollPosition = window.scrollY + window.innerHeight;
    const documentHeight = document.documentElement.scrollHeight;
    const buffer = 200; // pixels from bottom
    const nearBottom = scrollPosition >= (documentHeight - buffer);
    console.log('Scroll check:', {
        scrollPosition,
        documentHeight,
        buffer,
        nearBottom
    });
    return nearBottom;
}

// Debounced scroll handler
let scrollTimeout;
window.addEventListener('scroll', () => {
    if (scrollTimeout) {
        clearTimeout(scrollTimeout);
    }

    scrollTimeout = setTimeout(() => {
        if (!endOfCards && !loading && isNearBottom()) {
            console.log('Triggering card fetch');
            fetchMoreCards();
        }
    }, 150);
});

// Initial load handler
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page loaded - Infinite scroll ready');
});