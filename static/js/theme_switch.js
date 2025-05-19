// Wait for DOM to load
document.addEventListener('DOMContentLoaded', function() {
    const toggle = document.getElementById('gameToggle');

    // Set initial toggle state based on current game mode
    if (document.body.classList.contains('lorcana-theme')) {
        toggle.checked = true;
    }

    toggle.addEventListener('change', function() {
        if (toggle.checked) {
            switchToLorcana();
        } else {
            switchToMTG();
        }
    });
});

function switchToMTG() {
    // Change frontend theme
    document.body.classList.remove('lorcana-theme');
    document.body.classList.add('mtg-theme');

    // Send request to Flask to update session/backend
    fetch('/switch_game_mode', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: 'mtg' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Reload the page to get the new CSS and content
            window.location.reload();
        }
    })
    .catch(error => console.error('Error:', error));
}

function switchToLorcana() {
    // Change frontend theme
    document.body.classList.remove('mtg-theme');
    document.body.classList.add('lorcana-theme');

    // Send request to Flask to update session/backend
    fetch('/switch_game_mode', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: 'lorcana' })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Reload the page to get the new CSS and content
            window.location.reload();
        }
    })
    .catch(error => console.error('Error:', error));
}