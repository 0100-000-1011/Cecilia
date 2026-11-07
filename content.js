/* ============================================================
 *  全站内容都在这个文件里。
 *  改完保存 → 提交到 GitHub → 几十秒后网页自动更新，二维码不用换。
 *  可用的块类型：heading / text / quote / image / gallery / audio / divider / links
 *  各类型的写法见下面示例，或者看 README.md
 * ============================================================ */

window.PAGE = {

  /* 浏览器标签页标题（分享到微信时也显示这个） */
  siteTitle: "秋日手记",
  description: "一些照片，一段声音，和一封写给你的短信。",

  /* 首屏：大图 + 标题 */
  hero: {
    cover: "assets/cover.jpg",
    kicker: "2026 · 十一月",
    title: "秋日手记",
    subtitle: "一些照片，一段声音，\n和一封写给你的短信。",
    meta: "文 / 图 / 声音 · Eason"
  },

  /* 正文，从上往下依次排列 */
  blocks: [

    { type: "text", text:
      "这是一页可以自己编辑的静态网页：文字、照片、录音都放在同一个链接里，扫一下二维码就能打开。\n\n" +
      "下面这些内容都是**示例**，把 `content.js` 里的文字和 `assets/` 里的文件换成你自己的就行。" },

    { type: "heading", level: 2, text: "十一月的第一个周末" },

    { type: "text", text:
      "天气忽然就凉了下来。中午的光还是暖的，落到桌上像一层薄薄的蜜，到了四点半就整片暗下去。" +
      "我在窗边坐了很久，什么也没做，只是看楼下那棵树一片一片地把叶子交出去。" },

    { type: "image", src: "assets/photo-1.jpg", alt: "傍晚的窗台", caption: "放大看，光里都是灰。" },

    { type: "quote", text: "秋天不是季节，是一种把声音调低的办法。", cite: "—— 某人" },

    { type: "heading", level: 2, text: "存下来的三张" },

    { type: "gallery", items: [
      { src: "assets/photo-1.jpg", alt: "窗台", caption: "窗台，下午四点" },
      { src: "assets/photo-2.jpg", alt: "走廊", caption: "走廊尽头" },
      { src: "assets/photo-3.jpg", alt: "桌面", caption: "桌上的东西" }
    ]},

    { type: "text", text:
      "点开任意一张可以全屏看。图片建议压到 `1600px` 宽、`200KB` 以内，手机加载会快很多。" },

    { type: "heading", level: 2, text: "说一句话" },

    { type: "text", text: "有时候文字不够用。下面这段是机器合成的示例音频，换成你自己的录音（`m4a` / `mp3`）即可：" },

    { type: "audio", items: [
      { src: "assets/voice-1.m4a", title: "一段示例录音", desc: "点左边的圆钮播放，进度条可以拖动。" }
    ]},

    { type: "divider" },

    { type: "text", text:
      "要换成自己的内容，只需要做两件事：\n\n" +
      "1. 把照片和音频放进 `assets/` 文件夹；\n" +
      "2. 回来改这个文件里的标题、正文和文件名。\n\n" +
      "改完之后，二维码指向的网址没有变，所以**不用重新生成二维码**。" },

    { type: "links", items: [
      { label: "查看 README 使用说明", href: "https://docs.github.com/pages" }
    ]}

  ],

  footer: {
    note: "把链接或二维码发给朋友，用手机相机扫一下就能打开。",
    /* 生成二维码后（python3 make_qr.py 网址）会自动出现在这里，不用改 */
    qr: "assets/qr.png"
  }
};
