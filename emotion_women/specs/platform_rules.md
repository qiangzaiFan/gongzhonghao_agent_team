# 平台规则

## 微信公众号

- 默认只生成本地 Markdown 草稿。
- 只有显式使用 `--publish` 或用户明确说“发到草稿箱”时，才推送到微信公众号草稿箱。
- 发布只进入草稿箱，不直接群发。
- 发布前必须通过：
  - `python validate_article_images.py <文章路径>`
  - `python quality_gate.py <文章路径>`
- `.mcp.json` 存放真实凭证，必须保持本地忽略；`.mcp.example.json` 只能放占位符。

## 其他

- 没有明确发布指令时，只生成本地文件。
- 不维护其他平台发布、同步或改写规则。
