<?php
/**
 * NEX Hotel - PHP Booking Website
 * One-click installation script
 */

require_once 'config.php';
require_once 'includes/functions.php';

session_start();

// Check if installation is needed
if (!file_exists('installed.lock')) {
    header('Location: install.php');
    exit;
}

$page = isset($_GET['page']) ? $_GET['page'] : 'home';

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo SITE_NAME; ?> - Hotel Booking</title>
    <link rel="stylesheet" href="assets/css/style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <nav class="navbar">
                <div class="logo">
                    <h1><?php echo SITE_NAME; ?></h1>
                </div>
                <ul class="nav-menu">
                    <li><a href="?page=home">Home</a></li>
                    <li><a href="?page=rooms">Rooms</a></li>
                    <li><a href="?page=booking">Book Now</a></li>
                    <li><a href="?page=contact">Contact</a></li>
                    <?php if (isset($_SESSION['user'])): ?>
                        <li><a href="?page=dashboard">Dashboard</a></li>
                        <li><a href="?page=logout">Logout</a></li>
                    <?php else: ?>
                        <li><a href="?page=login">Login</a></li>
                    <?php endif; ?>
                </ul>
            </nav>
        </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
        <?php
        switch ($page) {
            case 'home':
                include 'pages/home.php';
                break;
            case 'rooms':
                include 'pages/rooms.php';
                break;
            case 'booking':
                include 'pages/booking.php';
                break;
            case 'contact':
                include 'pages/contact.php';
                break;
            case 'login':
                include 'pages/login.php';
                break;
            case 'dashboard':
                include 'pages/dashboard.php';
                break;
            default:
                include 'pages/404.php';
        }
        ?>
    </main>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <p>&copy; <?php echo date('Y'); ?> <?php echo SITE_NAME; ?>. All rights reserved.</p>
            <p>Powered by NEX Hotel AI</p>
        </div>
    </footer>

    <script src="assets/js/main.js"></script>
</body>
</html>