<?php
/**
 * Booking Page with AI Assistant
 */

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Process booking
    $data = [
        'guest_name' => $_POST['name'],
        'phone' => $_POST['phone'],
        'email' => $_POST['email'],
        'check_in' => $_POST['check_in'],
        'check_out' => $_POST['check_out'],
        'room_type' => $_POST['room_type'],
        'num_adults' => $_POST['adults'],
        'num_children' => $_POST['children']
    ];
    
    // Call API
    $result = api_call('POST', '/api/bookings', $data);
    
    if ($result['success']) {
        $booking_ref = $result['data']['booking_ref'];
        $_SESSION['booking_success'] = $booking_ref;
        header('Location: ?page=booking-confirm&ref=' . $booking_ref);
        exit;
    } else {
        $error = $result['message'];
    }
}
?>

<section class="booking-section">
    <div class="container">
        <h1>Book Your Stay</h1>
        
        <?php if (isset($error)): ?>
            <div class="alert alert-danger"><?php echo $error; ?></div>
        <?php endif; ?>
        
        <div class="booking-grid">
            <!-- AI Chat Assistant -->
            <div class="ai-assistant">
                <div class="chat-header">
                    <i class="fas fa-robot"></i>
                    <h3>AI Booking Assistant</h3>
                </div>
                <div class="chat-messages" id="chat-messages">
                    <div class="message ai-message">
                        Hi! I'm your AI booking assistant. I can help you find the perfect room. Just tell me:
                        <ul>
                            <li>When do you want to check in?</li>
                            <li>How many nights?</li>
                            <li>How many guests?</li>
                            <li>Any room preferences?</li>
                        </ul>
                    </div>
                </div>
                <div class="chat-input">
                    <input type="text" id="ai-input" placeholder="Type your request... e.g., 'Book 2 deluxe rooms for 3 nights'">
                    <button onclick="sendAICommand()"><i class="fas fa-paper-plane"></i></button>
                </div>
            </div>
            
            <!-- Traditional Booking Form -->
            <div class="booking-form">
                <form method="POST">
                    <h2>Or Fill Form Manually</h2>
                    
                    <div class="form-group">
                        <label>Full Name *</label>
                        <input type="text" name="name" required>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label>Phone *</label>
                            <input type="tel" name="phone" required>
                        </div>
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" name="email">
                        </div>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label>Check-In *</label>
                            <input type="date" name="check_in" required>
                        </div>
                        <div class="form-group">
                            <label>Check-Out *</label>
                            <input type="date" name="check_out" required>
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Room Type</label>
                        <select name="room_type">
                            <option value="">Any Available</option>
                            <option value="Deluxe">Deluxe</option>
                            <option value="AC">AC</option>
                            <option value="Non-AC">Non-AC</option>
                            <option value="Suite">Suite</option>
                        </select>
                    </div>
                    
                    <div class="form-row">
                        <div class="form-group">
                            <label>Adults</label>
                            <input type="number" name="adults" value="1" min="1">
                        </div>
                        <div class="form-group">
                            <label>Children</label>
                            <input type="number" name="children" value="0" min="0">
                        </div>
                    </div>
                    
                    <button type="submit" class="btn-primary">Book Now</button>
                </form>
            </div>
        </div>
    </div>
</section>

<script>
function sendAICommand() {
    const input = document.getElementById('ai-input');
    const command = input.value.trim();
    
    if (!command) return;
    
    // Add user message
    addMessage(command, 'user');
    input.value = '';
    
    // Call AI API
    fetch('<?php echo API_URL; ?>/api/ai/command', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command: command })
    })
    .then(res => res.json())
    .then(data => {
        addMessage(data.response, 'ai');
        
        // Auto-fill form if booking details extracted
        if (data.action === 'booking' && data.entities) {
            fillFormFromAI(data.entities);
        }
    })
    .catch(err => {
        addMessage('Sorry, I encountered an error. Please try again.', 'ai');
    });
}

function addMessage(text, type) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    messageDiv.textContent = text;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function fillFormFromAI(entities) {
    if (entities.check_in) document.querySelector('[name="check_in"]').value = entities.check_in;
    if (entities.check_out) document.querySelector('[name="check_out"]').value = entities.check_out;
    if (entities.room_type) document.querySelector('[name="room_type"]').value = entities.room_type;
    if (entities.adults) document.querySelector('[name="adults"]').value = entities.adults;
    if (entities.children) document.querySelector('[name="children"]').value = entities.children;
}

// Allow Enter key to send message
document.getElementById('ai-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendAICommand();
    }
});
</script>