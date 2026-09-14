# ComfyUI-FrameSelector

**视频逐帧提取 + 暂停选图继续运行** 的 ComfyUI 自定义节点插件。
Extract **every frame** of a video, **pause** the workflow mid-run, let you **pick the images**
you want, and continue the next step with only the selected frames.

## 节点 / Nodes

| 节点 | 显示名 | 说明 |
|---|---|---|
| `VideoFrameExtractor` | Video Frame Extractor (视频逐帧提取) | 用 OpenCV 解码视频每一帧，输出 `IMAGE` 批次 + `frame_count` + `fps`。支持 `force_rate`、`skip_first_frames`、`select_every_nth`、`max_frames`、`width/height` 缩放；自动兼容 Windows 中文路径。 |
| `FrameSelector` | Image Selector (图像选择器) | 运行到此处**自动暂停**，弹出网页选图面板（缩略图网格 / 多选 / 全选 / 清空）。点击「确认继续」后仅把选中帧传给下游；「取消当前运行」中断本次运行。`mode`: Always Pause / Pause If Multiple / Never Pause；`preview_rescale` 控制缩略图大小；`timeout` 秒（0=无限等待）。 |

> `FrameSelector` 的输入是通用 `IMAGE`，因此也可以接 **VideoHelperSuite 的 Load Video** 等任何图像批次来源。

## 安装 / Installation

**方式一：ComfyUI Manager**：搜索 `ComfyUI-FrameSelector` → Install。

**方式二：手动**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-github-username/ComfyUI-FrameSelector.git
cd ComfyUI-FrameSelector
pip install -r requirements.txt     # 使用整合包时请用对应 python 环境
# 重启 ComfyUI

```

## 使用 / Usage

1. 添加 `Video Frame Extractor (视频逐帧提取)`，填入视频绝对路径（或改用 VHS 的 Load Video）。
2. 将 `images` 输出连到 `Image Selector (图像选择器)`。
3. 选择器输出连到下游任意节点（PreviewImage / SaveImage / 放大 / 重绘 …）。
4. 点击 **Queue Prompt**：运行到选择器时自动弹出「请选择图片以继续」面板。
5. 点击缩略图勾选/取消（默认全选），点 **确认继续 ✔**，工作流带着选中的帧继续执行。
6. 需要放弃时点 **取消当前运行**（节点上的按钮同样有效）。

示例工作流见 [`workflows/example_extract_and_select.json`](workflows/example_extract_and_select.json)（API 格式，可直接 POST 到 `/prompt` 或用 Manager 导入）。

## 工作原理 / How it works

- 节点执行时在 **prompt 工作线程** 上用 `threading.Event` 阻塞等待（本地单用户场景安全）。
- Python 端把输入帧编码为 JPEG 预览存于内存，通过 HTTP 路由提供：
  - `GET /frame_selector/status?node_id=` 预览是否就绪
  - `GET /frame_selector/img?node_id=&i=` 第 i 张预览图
  - `POST /frame_selector/select` 提交选中索引，释放阻塞
  - `POST /frame_selector/cancel` 取消运行（抛出 `InterruptProcessingException`）
- 前端通过 WebSocket 事件 `frame_selector_wait` 自动打开选图弹窗；运行结束/中断/报错时自动关闭。

## 注意 / Notes

- 等待选图期间该次 prompt 占用执行线程，队列中的其他任务会排队——这是“暂停”的预期行为；可设置 `timeout` 防止永久等待。
- 长视频帧数很多时内存占用大，建议配合 `force_rate` / `max_frames` / `select_every_nth` 抽帧。
- 预览图为 JPEG（仅用于选择界面），下游拿到的是**原始精度**的帧张量。

## License

MIT © 2026 ComfyUI-FrameSelector Contributors