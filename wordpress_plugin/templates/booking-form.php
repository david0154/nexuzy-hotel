<?php
/**
 * NEX Hotel AI - WordPress Booking Form Template
 */
?>

<div class="nex-hotel-booking" id="nex-hotel-booking">
    <?php if ($atts['show_ai']): ?>
    <div class="nex-ai-assistant">
        <div class="nex-chat-header">
            <i class="dashicons dashicons-admin-users"></i>
            <h3><?php _e('AI Booking Assistant', 'nex-hotel-ai'); ?></h3>
        </div>
        <div class="nex-chat-messages" id="nex-chat-messages">
            <div class="nex-message nex-ai-message">
                <?php _e('Hi! I can help you book a room. Just tell me your requirements!', 'nex-hotel-ai'); ?>
            </div>
        </div>
        <div class="nex-chat-input">
            <input type="text" id="nex-ai-input" placeholder="<?php _e('Type your request...', 'nex-hotel-ai'); ?>">
            <button type="button" id="nex-ai-send"><?php _e('Send', 'nex-hotel-ai'); ?></button>
        </div>
    </div>
    <?php endif; ?>
    
    <div class="nex-booking-form">
        <h2><?php _e('Book Your Room', 'nex-hotel-ai'); ?></h2>
        <form id="nex-booking-form" method="POST">
            <div class="nex-form-group">
                <label><?php _e('Full Name', 'nex-hotel-ai'); ?> *</label>
                <input type="text" name="name" required>
            </div>
            
            <div class="nex-form-row">
                <div class="nex-form-group">
                    <label><?php _e('Phone', 'nex-hotel-ai'); ?> *</label>
                    <input type="tel" name="phone" required>
                </div>
                <div class="nex-form-group">
                    <label><?php _e('Email', 'nex-hotel-ai'); ?></label>
                    <input type="email" name="email">
                </div>
            </div>
            
            <div class="nex-form-row">
                <div class="nex-form-group">
                    <label><?php _e('Check-In', 'nex-hotel-ai'); ?> *</label>
                    <input type="date" name="check_in" required>
                </div>
                <div class="nex-form-group">
                    <label><?php _e('Check-Out', 'nex-hotel-ai'); ?> *</label>
                    <input type="date" name="check_out" required>
                </div>
            </div>
            
            <div class="nex-form-group">
                <label><?php _e('Room Type', 'nex-hotel-ai'); ?></label>
                <select name="room_type">
                    <option value=""><?php _e('Any Available', 'nex-hotel-ai'); ?></option>
                    <option value="Deluxe"><?php _e('Deluxe', 'nex-hotel-ai'); ?></option>
                    <option value="AC"><?php _e('AC', 'nex-hotel-ai'); ?></option>
                    <option value="Non-AC"><?php _e('Non-AC', 'nex-hotel-ai'); ?></option>
                    <option value="Suite"><?php _e('Suite', 'nex-hotel-ai'); ?></option>
                </select>
            </div>
            
            <div class="nex-form-row">
                <div class="nex-form-group">
                    <label><?php _e('Adults', 'nex-hotel-ai'); ?></label>
                    <input type="number" name="adults" value="1" min="1">
                </div>
                <div class="nex-form-group">
                    <label><?php _e('Children', 'nex-hotel-ai'); ?></label>
                    <input type="number" name="children" value="0" min="0">
                </div>
            </div>
            
            <button type="submit" class="nex-btn-primary"><?php _e('Book Now', 'nex-hotel-ai'); ?></button>
        </form>
    </div>
</div>

<script>
jQuery(document).ready(function($) {
    $('#nex-ai-send').on('click', function() {
        var command = $('#nex-ai-input').val().trim();
        if (!command) return;
        
        // Add user message
        $('#nex-chat-messages').append('<div class="nex-message nex-user-message">' + command + '</div>');
        $('#nex-ai-input').val('');
        
        // Call AI
        $.ajax({
            url: nexHotelAjax.ajax_url,
            type: 'POST',
            data: {
                action: 'nex_hotel_command',
                nonce: nexHotelAjax.nonce,
                command: command
            },
            success: function(response) {
                if (response.success) {
                    $('#nex-chat-messages').append('<div class="nex-message nex-ai-message">' + response.data.response + '</div>');
                    $('#nex-chat-messages').scrollTop($('#nex-chat-messages')[0].scrollHeight);
                }
            }
        });
    });
    
    $('#nex-ai-input').on('keypress', function(e) {
        if (e.which === 13) {
            $('#nex-ai-send').click();
        }
    });
});
</script>