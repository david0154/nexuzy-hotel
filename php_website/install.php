<?php
/**
 * NEX Hotel - One-Click Installation
 */

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Get form data
    $site_name = $_POST['site_name'];
    $keywords = $_POST['keywords'];
    $admin_email = $_POST['admin_email'];
    $admin_password = password_hash($_POST['admin_password'], PASSWORD_DEFAULT);
    $db_host = $_POST['db_host'];
    $db_name = $_POST['db_name'];
    $db_user = $_POST['db_user'];
    $db_pass = $_POST['db_pass'];
    $api_url = $_POST['api_url'] ?? 'http://localhost:8000';
    
    // Create config.php
    $config_content = "<?php\n";
    $config_content .= "define('SITE_NAME', '{$site_name}');\n";
    $config_content .= "define('SITE_KEYWORDS', '{$keywords}');\n";
    $config_content .= "define('DB_HOST', '{$db_host}');\n";
    $config_content .= "define('DB_NAME', '{$db_name}');\n";
    $config_content .= "define('DB_USER', '{$db_user}');\n";
    $config_content .= "define('DB_PASS', '{$db_pass}');\n";
    $config_content .= "define('API_URL', '{$api_url}');\n";
    $config_content .= "?>";
    
    file_put_contents('config.php', $config_content);
    
    // Create database connection
    try {
        $pdo = new PDO("mysql:host={$db_host};dbname={$db_name}", $db_user, $db_pass);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        
        // Create tables
        $sql = file_get_contents('install/database.sql');
        $pdo->exec($sql);
        
        // Create admin user
        $stmt = $pdo->prepare("INSERT INTO users (email, password, role) VALUES (?, ?, 'admin')");
        $stmt->execute([$admin_email, $admin_password]);
        
        // Create lock file
        file_put_contents('installed.lock', date('Y-m-d H:i:s'));
        
        header('Location: index.php?installed=1');
        exit;
        
    } catch (PDOException $e) {
        $error = "Database error: " . $e->getMessage();
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEX Hotel - Installation</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .install-container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); max-width: 600px; width: 100%; }
        h1 { color: #333; margin-bottom: 30px; text-align: center; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; color: #555; font-weight: 500; }
        input, select { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        input:focus { border-color: #667eea; outline: none; }
        button { width: 100%; padding: 15px; background: #667eea; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: 600; cursor: pointer; transition: 0.3s; }
        button:hover { background: #5568d3; }
        .error { background: #fee; color: #c33; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .section-title { color: #667eea; font-size: 18px; margin: 30px 0 15px; padding-bottom: 10px; border-bottom: 2px solid #eee; }
    </style>
</head>
<body>
    <div class="install-container">
        <h1>🏨 NEX Hotel Installation</h1>
        
        <?php if (isset($error)): ?>
            <div class="error"><?php echo $error; ?></div>
        <?php endif; ?>
        
        <form method="POST">
            <div class="section-title">Website Settings</div>
            
            <div class="form-group">
                <label>Website Name</label>
                <input type="text" name="site_name" required placeholder="My Hotel">
            </div>
            
            <div class="form-group">
                <label>Keywords (for SEO)</label>
                <input type="text" name="keywords" placeholder="hotel, booking, accommodation">
            </div>
            
            <div class="section-title">Admin Account</div>
            
            <div class="form-group">
                <label>Admin Email</label>
                <input type="email" name="admin_email" required placeholder="admin@example.com">
            </div>
            
            <div class="form-group">
                <label>Admin Password</label>
                <input type="password" name="admin_password" required placeholder="Strong password">
            </div>
            
            <div class="section-title">Database Settings</div>
            
            <div class="form-group">
                <label>Database Host</label>
                <input type="text" name="db_host" value="localhost" required>
            </div>
            
            <div class="form-group">
                <label>Database Name</label>
                <input type="text" name="db_name" required placeholder="nex_hotel_db">
            </div>
            
            <div class="form-group">
                <label>Database Username</label>
                <input type="text" name="db_user" required placeholder="root">
            </div>
            
            <div class="form-group">
                <label>Database Password</label>
                <input type="password" name="db_pass" placeholder="Leave blank if none">
            </div>
            
            <div class="section-title">API Settings</div>
            
            <div class="form-group">
                <label>API URL (NEX Hotel AI API)</label>
                <input type="text" name="api_url" value="http://localhost:8000" placeholder="http://localhost:8000">
            </div>
            
            <button type="submit">✓ Install NEX Hotel</button>
        </form>
    </div>
</body>
</html>