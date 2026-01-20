# Screenshot Translator (Qwen3-VL-30B-A3B)

<img width="640" height="521" alt="Image" src="https://github.com/user-attachments/assets/f24ef322-08b5-48e6-aa54-71b9e06d7401" />

![Image](https://github.com/user-attachments/assets/2939810b-8c72-4e91-9964-d6fac526c736)

このリポジトリには3つの使い方があります。
1) Web UI: クリップボード貼り付け画像を OCR + 英→日翻訳して Markdown 表示
2) Windows 常駐クライアント: 画面上の範囲選択 → スクショ → OCR + 翻訳をオーバーレイ表示
3) Ubuntu Gnome Extension: 画面上の範囲選択 → スクショ → OCR + 翻訳 (Monitor Modeで自動読み上げ対応)

※ Windows 常駐クライアントは **Windows + WSL2 前提**です（Windows側から WSL2 上の FastAPI に接続します）。

※ Ubuntu Gnome Extension は Ubuntu (Gnome Shell) 環境用です。

## 要件
- CUDA 対応 GPU (例: CUDA 13 / nvcc 13.0.88)
- `uv` (Python パッケージマネージャ) がホストにインストール済み
- 下の２つのモデルファイルを[リンク先からダウンロード](https://huggingface.co/unsloth/Qwen3-VL-30B-A3B-Instruct-GGUF/tree/main)して、ローカル（./models/フォルダを作ってその中）に配置
  - [`models/Qwen3-VL-30B-A3B-Instruct-UD-Q4_K_XL.gguf`](https://huggingface.co/unsloth/Qwen3-VL-30B-A3B-Instruct-GGUF/blob/main/Qwen3-VL-30B-A3B-Instruct-UD-Q4_K_XL.gguf)
  - [`models/mmproj-F32.gguf`](https://huggingface.co/unsloth/Qwen3-VL-30B-A3B-Instruct-GGUF/blob/main/mmproj-F32.gguf)
- **音声読み上げ (TTS)**:
  - バックエンド起動時に `Kokoro-82M` (約300MB) が自動でダウンロードされます。
  - 音声再生のために、ホスト側に `libportaudio2` や `aplay` (ALSA) が必要です（Ubuntu Desktopなら通常は入っています）。

## 使い方
1. llama.cpp を CUDA ビルド
   ```bash
   ./app/scripts/build_llama.sh
   ```
   - `GGML_CUDA=ON` のみでビルドし、`LLAMA_CURL=OFF` でlibcurl未インストール環境でも通るようにしています。
   - 並列ビルドは `JOBS` 環境変数で上書き可能（既定は `nproc` があればその値、なければ4）。
   - 必要に応じて `LLAMA_REPO` / `LLAMA_DIR` を上書きしてください。
2. モデルを `models/` 配下へ配置 (パスは環境変数で変更可)。
3. サーバー起動
   ```bash
   ./start.sh
   ```
   - デフォルト: llama-server 8009, Web UI 8012, ctx=8192。
   - VRAMが少ない場合は起動時に `LLAMA_CTX` を下げて起動できます（例: `LLAMA_CTX=4096 ./start.sh`）。
   - 既存の llama-server を使う場合: `SKIP_LLAMACPP=1 LLAMA_SERVER_URL=http://127.0.0.1:8009 ./start.sh`

## 主な環境変数
- `WEB_PORT` (既定: 8012)
- `LLAMA_PORT` (既定: 8009)
- `LLAMA_MODEL` (既定: models/Qwen3-VL-30B-A3B-Instruct-UD-Q4_K_XL.gguf)
- `LLAMA_MMPROJ` (既定: models/mmproj-F32.gguf)
- `LLAMA_CTX` (既定: 8192)
- `LLAMA_BIN` (既定: ./llama.cpp/build/bin/llama-server)
- `SKIP_LLAMACPP`=1 で llama-server 起動をスキップ

### `LLAMA_CTX` について（VRAM調整）
- `LLAMA_CTX` は **llama.cpp の `llama-server` を起動する際の `-c`** に渡され、主に KV cache のサイズに効くため VRAM 使用量に影響します。
- `LLAMA_CTX` を変更してVRAM使用量を変えたい場合は、**llama-server を起動し直す必要があります**（FastAPI側の環境変数だけ変えてもVRAMは変わりません）。
- `SKIP_LLAMACPP=1` で既存の llama-server を使う場合、その既存プロセスが `-c` で起動された値が有効になります。

## フロントエンドの使い方
- ブラウザで `http://localhost:8012` にアクセス。
- 画像を **貼り付け** (Ctrl+V) するかドラッグ&ドロップ。
- 任意で追加指示を入力し「再送信」。
- 返ってきた Markdown を「コピー」ボタンで取得可能。
- CSS で横に長い行も折り返して表示。

## アーキテクチャ
- `llama.cpp` の `llama-server --api` を常駐させ、OpenAI 互換 `/v1/chat/completions` でマルチモーダル推論。
- FastAPI (ポート 8012) が画像を PNG に正規化 → llama-server へ base64 画像付きメッセージ送信。
- 応答 Markdown をそのまま表示 (要約禁止プロンプトを付与)。
- Windows 常駐クライアントは `windows/OverlayClient` にあり、Ctrl+Alt押下/離しでROIを取得して `/api/v1/ocr_translate_with_grounding` に送信する。

## Windows 常駐クライアント（WPF）
- 参照先: `windows/OverlayClient`
- 前提: Windows 10/11 + .NET 8 SDK（`dotnet --version` で確認）
- WSL2でこのリポジトリをCloneした場合は、windowsフォルダをWindows側にコピーしてビルド・実行してください。
- 先に WSL 側の FastAPI を起動しておく（`./start.sh`、ポート 8012）。
- ビルド:
  ```powershell
  cd windows/OverlayClient
  dotnet build
  ```
- 実行:
  ```powershell
  dotnet run
  ```
- 配布用にまとめる:
  ```powershell
  dotnet publish -c Release -o output
  ```
  - `output/` に実行ファイル一式が出力されます（`settings.json` も同梱）。
- `settings.json` は exe と同じフォルダに置かれ、ビルド出力に同梱されます。
- WSL 側に繋がらない場合は `settings.json` の `server.base_url` を確認してください。
- 既定は **Ctrl+Altを押しながらドラッグし、キーを離すと**矩形ROI指定 → 翻訳実行です（Ctrlのみ/Altのみは設定で変更可）。
- 既定で ROI は **赤枠で一瞬表示**されます（`overlay.preview.show_roi_preview`）。
- Ctrl押下中のリアルタイム枠表示は `overlay.preview.live_preview` で切替できます。
- オーバーレイは「×」で閉じられます（アプリ自体の終了はトレイメニューの Quit）。

## Ubuntu Gnome Extension (Screenshot Translator)
Ubuntu (Gnome Shell) 環境向けの専用拡張機能です。Windows 版とは操作感が異なります。
バージョン19以降、**トップバーのメニューからモード切替**が可能になりました。

### 前提
- Python バックエンド (`./start.sh`) が `127.0.0.1:8012` で起動している必要があります。

### インストール方法
リポジトリ内の拡張機能をローカルの拡張機能ディレクトリにコピーしてインストールします。
**注意**: Wayland 環境での更新不具合を防ぐため、シンボリックリンクではなく**コピー**を推奨しています。

※ `gnome-extension/metadata.json` 内の UUID とディレクトリ名は一致させる必要があります。

```bash
# ディレクトリ作成 (例: screenshot-translator@<your-username>)
# 注意: <your-username> の部分は metadata.json の uuid の @ 以降と一致させてください
mkdir -p ~/.local/share/gnome-shell/extensions/screenshot-translator@<your-username>

# ファイルのコピー (更新時もこのコマンドを実行してください)
cp -r gnome-extension/* ~/.local/share/gnome-shell/extensions/screenshot-translator@<your-username>/
```

### 有効化
インストール後、Gnome Shell を再読み込みする必要があります。
- **Wayland (Ubuntu 標準)**: 一度ログアウトして、再度ログインしてください。
- **X11**: `Alt` + `F2` を押し、`r` を入力して Enter。

再読み込み後、「Extensions (拡張機能)」アプリまたは「Extension Manager」を開き、**Screenshot Translator** を有効にしてください。

### 使い方
画面上部（トップバー）に追加される **辞書アイコン「あ」** (または類似のアイコン) からモードを切り替えて使用します。

1. **モード選択**:
   トップバーのアイコンをクリックし、以下のいずれかを選択します。
   - **Text Overlay Mode (翻訳モード)** [デフォルト]: 選択範囲を翻訳して画面に表示します。
   - **TTS Monitor Mode (読み上げモード)**: 選択範囲を定期的に監視し、変化があった箇所を日本語で読み上げます。

2. **キャプチャ開始**:
   - ショートカット: **`Ctrl` + `Alt` + `S`**
   - 画面が少し暗くなり、マウスドラッグで範囲を選択します。

3. **Monitor Mode (読み上げ) の挙動**:
   - 選択後、バックグラウンドで **5秒ごとに** 選択範囲を監視します。
   - 監視中はトップバーのアイコンが赤くなり、メニューに「Stop Monitoring」が表示されます。
   - **新しいテキスト**（チャットの追記やスクロールなど）が検出されると、自動的に日本語で読み上げられます（**Kokoro-82M ONNX** 音声合成エンジンを使用）。
   - 停止するには、再度ショートカットを押して新しい範囲を選ぶか、メニューから「Stop Monitoring」を選択してください。

4. **Monitor Mode のリセット**:
   - 別の範囲を選択したい場合は、再度 **`Ctrl` + `Alt` + `S`** を押してください。古いモニタリングは停止し、新しい範囲で即座に開始されます。

### アンインストール (取り除き方)
拡張機能を削除するには、以下のディレクトリを削除し、Gnome Shell を再読み込みします。

```bash
rm -rf ~/.local/share/gnome-shell/extensions/screenshot-translator@<your-username>
```
その後、ログアウト/ログイン (または `Alt+F2 r`) してください。

### トラブルシューティング
- **更新が反映されない**: Wayland では `Alt+F2 r` が効かないことがあるため、ログアウト/ログインを試してください。
- **Pango エラー**: 古いバージョンがキャッシュされている可能性があります。一度アンインストール操作を行ってから再インストールしてください。


## 新API（WSL側）
- `GET /health`
- `POST /api/v1/ocr_translate_with_grounding`（`clean_image` (必須) と `guide_image` (任意) を multipart で送信）

## 開発メモ
- 依存は仮想環境内 (`uv sync`) のみでインストールされ、ホストには入れません。
- フロントはプレーン HTML/CSS/JS (ビルド不要)。
- Markdown レンダリングは軽量な独自実装で、コード/箇条書き/強調をサポート。

## 既知の注意点
- llama.cpp 初回起動時にモデルをロードするため、1 回目のリクエストは時間がかかります。モデルのロードが完了（ステータスに「準備完了 (ログより) / 起動中（API応答あり・モデル読み込み未確認）」と表示されます。）しても翻訳が実行されない場合は、お手数ですが、再度画像を張り付けてください。
- モデル読み込み中に画像を貼り付けると失敗する場合があります。ステータスが「準備完了」と表示されてから貼り付けてください。
- `LLAMA_CTX` を大きくすると VRAM 使用量が増えます。GPU メモリに合わせて起動時に調整してください。


