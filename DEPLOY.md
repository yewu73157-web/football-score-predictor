# 稳定公网部署

当前 `localhost.run` 是临时隧道，域名会变化，适合临时演示，不适合稳定使用。

稳定方案推荐：

## 方案 A：云平台部署

把本目录部署到 Render、Railway、Fly.io 或其他支持 Python Web 服务的平台。

项目已经包含：

- `requirements.txt`
- `Procfile`
- `runtime.txt`
- `render.yaml`
- Flask 入口：`app:app`

部署参数：

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

优点：

- 固定 HTTPS 地址
- 手机、电脑、任何网络都能访问
- 不依赖你本机一直开机

推荐 Render 部署步骤：

1. 注册或登录 Render。
2. 新建 `Web Service`。
3. 连接包含本项目的 GitHub 仓库，或用 Render Blueprint 读取 `render.yaml`。
4. 选择 Python 环境。
5. 填写：

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
```

6. 部署完成后，Render 会给一个固定 HTTPS 地址，例如：

```text
https://your-app-name.onrender.com
```

这个地址就可以直接发给别人，别人无需和你连接同一个 Wi-Fi，也不需要你电脑开机。

注意：

- 免费云平台可能休眠，首次打开会慢。
- 如果要长期稳定，建议用付费实例或绑定自己的域名。

## 方案 B：Cloudflare Tunnel + 自己的域名

适合你想继续让程序跑在自己电脑上，但需要固定网址。

需要：

- 一个域名
- Cloudflare 账号
- 在 Cloudflare 中创建 Named Tunnel

优点：

- 固定域名
- 不需要云服务器

限制：

- 电脑必须一直开机
- 本地网络断开时网站仍会不可用

## 本项目部署入口

Python 入口：

```text
app:app
```

Docker 部署：

```text
Dockerfile
```

依赖：

```text
requirements.txt
```
