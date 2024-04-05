## Description
CNDS2024ハンズオン用アプリケーション。 </br>
Python製[FastAPI](https://github.com/tiangolo/fastapi)による簡易APIサーバーです。ランダムに色(赤、青、緑)を返し、結果をRedisに保存します。

## Getting Started

### Run program in local(port: 8000)

```bash
docker compose up --build
```

## APIs
Swagger UI(`/docs`)は無効化しています。

### GET

- `/healthz`: ヘルスチェック用

    ```bash
    curl localhost:8000/healthz
    ```

- `/metrics`: Prometheusフォーマット形式によるmetrics出力

    ```bash
    curl localhost:8000/metrics
    ```

- `/api/color`: 赤、青、緑からランダムに色を返却

    ```bash
    curl localhost:8000/api/color
    ```

- `/api/stats`: 合計、および各色の取得回数を返却

    ```bash
    curl loalhost:8000/api/stats
    ```

## Development
Microsoftの[Devcontainer](https://github.com/devcontainers)環境下での開発となります。VSCodeの`Remote Development` extensionが入った状態で、コマンドパレットの`Reopen in Container`で本repositoryを開いて開発環境を構築してください。

### API server起動
Devcontainerを立ち上げるとRedisも自動的に立ち上がります。API serverは`src/`に移動後、`python main.py`にて起動してください。

### Redis serverへのアクセス
`redis-cli`インストール済みのため、`redis-cli -h redis`にてRedis serverへアクセスが可能です。

## その他
- main branchへマージ前のruff, pytest, mypy実行是非の確認は未実装のため、適宜追加(pre-cmmitかGitHub actions想定)