# 默认表宠源素材

这三款形象是在 VelaPet 项目内用 SVG 几何图形绘制的原创联调素材，没有下载第三方角色或调用 Seedream。源文件不含字体、外链或嵌入照片，可直接改色、改轮廓。

| ID | 名称 | 定位 |
| --- | --- | --- |
| nova-cat | 星云猫 | 默认，紫色、温暖安静 |
| biscuit-dog | 奶油犬 | 奶油色、活泼友好 |
| mint-rabbit | 薄荷兔 | 薄荷色、温柔耐心 |

形象与聊天人设独立，目录中推荐 persona_id 仅供 UI 参考，选择外观不会自动改人设或业务皮肤。

从仓库根目录导出：

```powershell
.\test-results\ai-backend-venv-host\Scripts\python.exe host/ai-backend/tools/export_default_pets.py
```

输出至 `assets/generated/default-pets/`，包括每款 avatar 128×128、home 240×240、skin 160×160 的透明 RGBA PNG、预览总图和带哈希的 manifest。导出是本地渲染，不是 AI 生图。输出目录依仓库规则被忽略，可随时从 SVG 重建；请将这套素材视为候选默认款，等待最终美术审核。

板端需要验证透明 PNG 解码和内存：240×240 RGBA 像素约 225 KiB，不含解码临时内存。必要时在资源构建阶段转换为设备支持的格式；不得直接认定这些 PNG 已能上板。
