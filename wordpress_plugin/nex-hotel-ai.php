<?php
/**
 * Plugin Name: NEX Hotel AI
 * Plugin URI: https://nexuzy.in/nex-hotel-ai
 * Description: Complete hotel booking system with AI assistant for WordPress
 * Version: 1.0.0
 * Author: Nexuzy Tech Pvt Ltd
 * Author URI: https://nexuzy.in
 * License: GPL v2 or later
 * Text Domain: nex-hotel-ai
 */

if (!defined('ABSPATH')) exit;

define('NEX_HOTEL_VERSION', '1.0.0');
define('NEX_HOTEL_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('NEX_HOTEL_PLUGIN_URL', plugin_dir_url(__FILE__));

class NEX_Hotel_AI {
    
    private static $instance = null;
    
    public static function get_instance() {
        if (self::$instance == null) {
            self::$instance = new self();
        }
        return self::$instance;
    }
    
    private function __construct() {
        add_action('init', [$this, 'init']);
        add_action('wp_enqueue_scripts', [$this, 'enqueue_scripts']);
        add_shortcode('nex_hotel_ai', [$this, 'render_booking_form']);
        add_action('admin_menu', [$this, 'admin_menu']);
        add_action('wp_ajax_nex_hotel_command', [$this, 'handle_ai_command']);
        add_action('wp_ajax_nopriv_nex_hotel_command', [$this, 'handle_ai_command']);
    }
    
    public function init() {
        // Initialize plugin
    }
    
    public function enqueue_scripts() {
        wp_enqueue_style('nex-hotel-css', NEX_HOTEL_PLUGIN_URL . 'assets/css/style.css', [], NEX_HOTEL_VERSION);
        wp_enqueue_script('nex-hotel-js', NEX_HOTEL_PLUGIN_URL . 'assets/js/main.js', ['jquery'], NEX_HOTEL_VERSION, true);
        
        wp_localize_script('nex-hotel-js', 'nexHotelAjax', [
            'ajax_url' => admin_url('admin-ajax.php'),
            'nonce' => wp_create_nonce('nex_hotel_nonce')
        ]);
    }
    
    public function render_booking_form($atts) {
        $atts = shortcode_atts([
            'api_url' => get_option('nex_hotel_api_url', 'http://localhost:8000'),
            'show_ai' => true
        ], $atts);
        
        ob_start();
        include NEX_HOTEL_PLUGIN_DIR . 'templates/booking-form.php';
        return ob_get_clean();
    }
    
    public function admin_menu() {
        add_menu_page(
            'NEX Hotel AI',
            'NEX Hotel',
            'manage_options',
            'nex-hotel',
            [$this, 'admin_page'],
            'dashicons-admin-home',
            30
        );
        
        add_submenu_page(
            'nex-hotel',
            'Settings',
            'Settings',
            'manage_options',
            'nex-hotel-settings',
            [$this, 'settings_page']
        );
    }
    
    public function admin_page() {
        include NEX_HOTEL_PLUGIN_DIR . 'admin/dashboard.php';
    }
    
    public function settings_page() {
        if (isset($_POST['nex_hotel_save_settings'])) {
            update_option('nex_hotel_api_url', sanitize_text_field($_POST['api_url']));
            update_option('nex_hotel_enable_ai', isset($_POST['enable_ai']));
            echo '<div class="updated"><p>Settings saved!</p></div>';
        }
        
        include NEX_HOTEL_PLUGIN_DIR . 'admin/settings.php';
    }
    
    public function handle_ai_command() {
        check_ajax_referer('nex_hotel_nonce', 'nonce');
        
        $command = sanitize_text_field($_POST['command']);
        $api_url = get_option('nex_hotel_api_url', 'http://localhost:8000');
        
        $response = wp_remote_post($api_url . '/api/ai/command', [
            'headers' => ['Content-Type' => 'application/json'],
            'body' => json_encode(['command' => $command]),
            'timeout' => 15
        ]);
        
        if (is_wp_error($response)) {
            wp_send_json_error(['message' => 'API connection failed']);
        }
        
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);
        
        wp_send_json_success($data);
    }
}

// Initialize plugin
NEX_Hotel_AI::get_instance();