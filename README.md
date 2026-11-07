# 图文 + 音频网页 · 扫码打开

一个纯静态页面：文字、照片、录音放在同一页，挂到 GitHub Pages 上，生成二维码，手机一扫就能看。
没有后端、没有数据库、不要服务器钱，改内容只要改一个文件。

> **本项目实际部署**
> 仓库：`0100-000-1011/Cecilia`，页面放在 `milkdragon/` 子目录里
> 线上网址：`https://0100-000-1011.github.io/Cecilia/milkdragon/`
> 生成二维码：`cd milkdragon && python3 make_qr.py https://0100-000-1011.github.io/Cecilia/milkdragon/`
> 根目录 `/` 没有首页，直接访问会是 404，属正常。要加别的子页面，照着 `milkdragon/` 再复制一个文件夹即可。

---

## 一、5 分钟上线

### 0. 先在本地看一眼

```bash
cd qr-page
python3 -m http.server 8000
```

浏览器打开 <http://localhost:8000>。想用手机看，用局域网 IP 访问 `http://192.168.x.x:8000`。

### 1. 在 GitHub 建仓库

- 打开 <https://github.com/new>
- **Repository name** 随便起，比如 `my-page`（建议全小写、用连字符）
- 选 **Public**（免费账号的 Pages 只能公开仓库发布；私人仓库需要 Pro）
- 不要勾选任何初始化文件，直接 Create

### 2. 把本地文件推上去

```bash
cd qr-page
git remote add origin https://github.com/<你的用户名>/my-page.git
git push -u origin main
```

> 推送时要求密码的话，这里要填 **Personal Access Token**（不是账号密码）：
> GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → 勾 `repo` → 生成，当密码粘贴。

### 3. 打开 Pages

- 仓库页 → **Settings** → 左侧 **Pages**
- **Source** 选 `Deploy from a branch`
- **Branch** 选 `main` + `/ (root)` → **Save**
- 等 30 秒到 1 分钟，页面上方会出现网址：

```
https://<你的用户名>.github.io/my-page/
```

**这个网址就是永久地址。以后改内容重新 push，网址不变，二维码也不用换。**

### 4. 生成二维码

```bash
python3 -m pip install -r requirements.txt     # 只需第一次
python3 make_qr.py https://<你的用户名>.github.io/my-page/
```

生成两个文件：

- `assets/qr.png` —— 网页页脚会自动显示它
- `assets/qr.svg` —— 矢量版，拿去印刷/做大图不糊

生成完再推一次（`git add . && git commit -m "add qr" && git push`），页脚就长出一张二维码。

> 也可以直接把 `assets/qr.png` 发给别人、贴到海报上、印在明信片上。二维码指向固定网址，跟页面内容无关。

---

## 二、改内容

### 方式一：写 Markdown（推荐）

编辑 `milkdragon/content.md`，改完一键上线：

```bash
./deploy.sh "这次改了什么"
```

（= 编译 `content.md` → `content.js` → 提交 → 推送，一步到位）

**头部配置**（`---` 之间）：

```yaml
title: 秋日手记          # 标签页标题 + 大标题
description: …           # 分享卡片描述
cover: assets/piggy.jpg  # 首屏大图
kicker: 2026 · 十一月     # 标题上方小字
subtitle: 第一行\n第二行   # 副标题，\n 换行
meta: 文 / 图 / 声音 · Eason
footer_note: …           # 页脚说明
```

**正文**就是标准 Markdown，另有三条约定：

| 写法 | 效果 |
|---|---|
| `![说明](assets/a.jpg "图注")` 单独一行 | 大图 + 图注，点击全屏 |
| 连续多行图片（每行一张） | 自动拼成图片网格 |
| `::: audio` <br> `assets/v.m4a \| 标题 \| 说明` <br> `:::` | 音频播放器 |

其余（`#` 标题、`**粗体**`、`> 引文`、`1. 列表`、`---` 分隔线、`[文字](链接)`、行内代码、表格）都按标准 Markdown 渲染。

> 注意：`content.js` 是编译产物，会被覆盖，**不要手改它**——内容只改 `content.md`。

### 方式二：直接改 content.js（进阶）

打开 `content.js`，改这几处就行：

```js
siteTitle: "秋日手记",          // 标签页标题、分享卡片标题
description: "…",               // 分享卡片描述

hero: {
  cover: "assets/cover.jpg",    // 首屏大图
  kicker: "2026 · 十一月",       // 小字眼（日期/栏目），可留空 ""
  title: "秋日手记",             // 大标题
  subtitle: "…\n…",             // 副标题，\n 换行
  meta: "文 / 图 / 声音 · Eason"
},

blocks: [ … ]                   // 正文，按顺序排
```

### 块类型速查

| type | 用途 | 写法 |
|---|---|---|
| `text` | 正文段落 | `{ type:"text", text:"第一段\n\n第二段" }` |
| `heading` | 小标题 | `{ type:"heading", level:2, text:"十一月的第一个周末" }`（`level:3` 是小一号） |
| `quote` | 引文 | `{ type:"quote", text:"…", cite:"—— 某人" }` |
| `image` | 单张大图 | `{ type:"image", src:"assets/a.jpg", alt:"", caption:"图注" }` |
| `gallery` | 图片网格 | `{ type:"gallery", items:[{src:"…", caption:"…"}, …] }` |
| `audio` | 音频播放器 | `{ type:"audio", items:[{src:"assets/v.m4a", title:"标题", desc:"说明"}] }` |
| `divider` | 分隔线 | `{ type:"divider" }` |
| `links` | 胶囊按钮 | `{ type:"links", items:[{label:"看看这个", href:"https://…"}] }` |

正文里可以用两种行内标记：`**加粗**` 和 `[文字](https://链接)`。

### 放自己的图 / 录音

1. 把文件丢进 `assets/` 文件夹（中文名也能用，但建议英文，避免链接转义）
2. 在 `content.js` 里写 `assets/文件名.jpg`

**图片**：宽度压到 1600px、单张 200KB 以内。命令行压图：

```bash
sips -Z 1600 photo.jpg                          # 只改尺寸
# 或者用 https://squoosh.app 手动压，效果更好
```

**音频**：`m4a` / `mp3` / `ogg` 都行，手机浏览器都支持。iPhone 录音（`.m4a`）直接可用；如果手上是 `.wav`：

```bash
afconvert -f m4af -d aac -b 64000 录音.wav assets/voice.m4a
```

一段 1 分钟的 m4a 大约 500KB，可以接受；整页总大小控制在 3MB 以内，手机扫码打开才够快。

---

## 三、目录结构

```
qr-page/
├── deploy.sh           ★ 一键更新（编译 + 提交 + 推送）
├── milkdragon/         子页面（线上 …/Cecilia/milkdragon/）
│   ├── content.md      ★ 所有内容在这里（Markdown）
│   ├── build.py        content.md → content.js
│   ├── content.js      编译产物，页面实际读取
│   ├── index.html      页面骨架（一般不用改）
│   ├── css/style.css   样式（颜色改文件顶部的变量）
│   ├── js/render.js    渲染 + 音频播放器 + 大图查看
│   ├── js/md-*.js      （无）Markdown 在编译期已转 HTML
│   ├── make_qr.py      网址 → 二维码
│   ├── requirements.txt
│   └── assets/         图片、音频、二维码
└── .nojekyll           告诉 GitHub Pages 别用 Jekyll 处理（保留，别删）
```

---

## 四、常见问题

**页脚没出现二维码？**
`assets/qr.png` 不存在，或者没 push 上去。跑一次 `make_qr.py` 再推。

**改了 content.js，网页没变？**
浏览器缓存。手机下拉刷新 / 微信里点右上角「刷新」。Pages 部署本身约 30 秒，可以在仓库 **Actions** 页看进度。

**想让二维码扫出来是自己的域名？**
仓库 Settings → Pages → Custom domain 填域名，然后重新跑 `make_qr.py https://你的域名/`。

**扫码后显示 404？**
仓库名和网址里的路径要一致：`https://用户名.github.io/仓库名/`（末尾斜杠别丢）。如果仓库名就叫 `用户名.github.io`，网址是 `https://用户名.github.io/`。

**内容有私密性吗？**
公开仓库 = 所有人可见，二维码只是「快捷入口」，不是权限。要私密内容别放这里。

**二维码能印多大？**
用 `assets/qr.svg`。印刷建议成品不小于 3cm × 3cm，四周留白别裁掉（脚本已留 3 个模块的白边）。
