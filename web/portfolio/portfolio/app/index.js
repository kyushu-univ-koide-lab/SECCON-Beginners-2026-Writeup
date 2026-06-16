const path = require("path");
const express = require("express");

const app = express();
const PORT = process.env.PORT || 33455;
const publicDir = path.join(__dirname, "public");

app.use(express.static(publicDir));

app.get("/admin", (req, res) => {
  res.status(403).send(`<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>403 Forbidden</title>
    <link rel="stylesheet" href="/styles.css">
  </head>
  <body>
    <main class="message">
      <p class="eyebrow">403 Forbidden</p>
      <h1>管理者だけが見られます</h1>
      <p>このページはまだ準備中です。</p>
      <a href="/">トップへ戻る</a>
    </main>
  </body>
</html>`);
});

app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
