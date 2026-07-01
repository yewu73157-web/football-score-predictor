# 足球杯比分预测模型

本地启动：

```powershell
python app.py
```

浏览器打开：

```text
http://127.0.0.1:8765
```

手机访问：

```powershell
.\start-mobile.ps1
```

脚本会显示类似下面的手机访问地址：

```text
http://192.168.x.x:8765/
```

手机和电脑需要连接同一个 Wi-Fi。如果手机打不开，通常是 Windows 防火墙拦截了 Python，需要允许 Python 访问专用网络。

任意网络公网访问：

```powershell
.\start-public.ps1
```

脚本会生成一个类似下面的公网地址：

```text
https://xxxx.lhr.life
```

保持脚本窗口打开，公网地址才有效。关闭窗口后，临时地址会失效；下次启动会生成新的地址。

如果需要稳定固定公网地址，请看：

```text
DEPLOY.md
```

临时公网隧道守护模式：

```powershell
.\start-public-watch.ps1
```

它会自动重连，并把当前可用地址写入：

```text
current-public-url.txt
```

但注意：这仍然不是固定域名。

说明：

- 只包含 2026 世界杯 32 强淘汰赛球队。
- 前端只能从下拉框选择球队，避免输入非本届淘汰赛队伍。
- 后端会联网搜索球队近况、伤停和预计阵容摘要。
- 模型使用国家队基础强度、淘汰赛保守系数、阵容风险搜索信号、泊松比分分布和 Dixon-Coles 低比分修正。
