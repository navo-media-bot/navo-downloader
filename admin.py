from flask import Flask, request, redirect, render_template_string
import os

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me")

HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Navo Admin</title>
<style>
body {
    margin: 0;
    background: #0f1115;
    color: white;
    font-family: Arial, sans-serif;
}
.container {
    max-width: 900px;
    margin: auto;
    padding: 20px;
}
h1 { margin-bottom: 25px; }
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fit,minmax(180px,1fr));
    gap: 15px;
}
.card {
    background: #181b22;
    border-radius: 15px;
    padding: 20px;
}
.number {
    font-size: 30px;
    font-weight: bold;
}
.status {
    color: #39d98a;
}
</style>
</head>

<body>
<div class="container">
<h1>🚀 Navo Admin</h1>

<div class="cards">

<div class="card">
<h3>🤖 Бот</h3>
<div class="number status">ONLINE</div>
</div>

<div class="card">
<h3>👥 Пользователи</h3>
<div class="number">0</div>
</div>

<div class="card">
<h3>📥 Загрузки</h3>
<div class="number">0</div>
</div>

<div class="card">
<h3>🚫 Заблокировано</h3>
<div class="number">0</div>
</div>

</div>

</div>
</body>
</html>
"""

LOGIN = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Navo Admin</title>
<style>
body {
    background:#0f1115;
    color:white;
    font-family:Arial;
    display:flex;
    justify-content:center;
    align-items:center;
    min-height:100vh;
}
.box {
    background:#181b22;
    padding:30px;
    border-radius:20px;
    width:280px;
}
input,button {
    width:100%;
    box-sizing:border-box;
    padding:13px;
    margin-top:12px;
    border:0;
    border-radius:10px;
}
button {
    background:#ffffff;
    cursor:pointer;
}
</style>
</head>
<body>
<div class="box">
<h2>🔐 Navo Admin</h2>
<form method="post">
<input type="password" name="password" placeholder="Пароль">
<button>Войти</button>
</form>
</div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            return render_template_string(HTML)

    return render_template_string(LOGIN)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
