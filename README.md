# raspberry-watchdog

Raspberry Pi上で動作するインターネット疎通監視ツール。設定したホストへ定期的にpingを実行し、疎通していれば緑LED、していなければ赤LEDを点灯する。systemdサービスとして常駐し、結果をログファイルに記録する（logrotateにより月次ローテーション）。

## 動作要件

- Raspberry Pi OS (Bookworm以降を推奨)
- Python 3
- ping疎通先LEDとGPIOへの配線（各LEDはGPIOピン→抵抗→LED→GNDの回路）

## インストール手順

1. 必要パッケージのインストール

   ```sh
   sudo apt update
   sudo apt install -y python3-gpiozero python3-lgpio
   ```

2. `pi`ユーザーが`gpio`グループに所属していることを確認

   ```sh
   groups pi
   # 含まれていない場合
   sudo usermod -aG gpio pi
   ```

3. プログラム一式を配置

   ```sh
   sudo mkdir -p /opt/raspberry-watchdog
   sudo cp watchdog.py /opt/raspberry-watchdog/
   ```

4. 設定ファイルを配置して編集（ping先ホストとGPIOピン番号を環境に合わせて変更）

   ```sh
   sudo mkdir -p /etc/raspberry-watchdog
   sudo cp config.ini /etc/raspberry-watchdog/
   sudo nano /etc/raspberry-watchdog/config.ini
   ```

5. ログ出力先ディレクトリを作成

   ```sh
   sudo mkdir -p /var/log/raspberry-watchdog
   sudo chown pi:pi /var/log/raspberry-watchdog
   ```

6. logrotate設定を配置

   ```sh
   sudo cp logrotate/raspberry-watchdog /etc/logrotate.d/raspberry-watchdog
   ```

7. systemdサービスを配置して起動

   ```sh
   sudo cp systemd/raspberry-watchdog.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now raspberry-watchdog
   ```

## 設定ファイル (`/etc/raspberry-watchdog/config.ini`)

| セクション | キー | 説明 |
| --- | --- | --- |
| network | host | ping先ホスト（IPまたはドメイン名） |
| network | interface | 疎通確認に使用するNIC名（例: `eth0`）。空欄の場合はOSのルーティングに従う |
| network | ping_count | 1回の確認で送信するping数 |
| network | ping_timeout | ping応答待ちタイムアウト（秒） |
| network | check_interval | 疎通確認の実行間隔（秒） |
| gpio | led_green_pin | 疎通OK時に点灯するLEDのBCM GPIO番号 |
| gpio | led_red_pin | 疎通NG時に点灯するLEDのBCM GPIO番号 |
| logging | log_file | ログファイルの出力先パス |
| logging | log_level | ログレベル（DEBUG/INFO/WARNING/ERROR） |

Wi-Fiを使わず有線LANのみで疎通確認したい場合は、`interface`に有線NICのインターフェース名を設定する。

```sh
# インターフェース名の確認（例: eth0, end0 など環境により異なる）
ip -o link show
```

```ini
[network]
interface = eth0
```

指定したインターフェースが存在しない、またはリンクダウンしている場合は`ping`が失敗し、通常の疎通NG時と同様に赤LED点灯・ログ記録が行われる。

## 動作確認

```sh
# サービス状態確認
sudo systemctl status raspberry-watchdog

# サービスログ（標準出力・エラー）確認
sudo journalctl -u raspberry-watchdog -f

# 疎通確認ログの確認
sudo tail -f /var/log/raspberry-watchdog/watchdog.log

# logrotate設定のドライラン確認
sudo logrotate -d /etc/logrotate.d/raspberry-watchdog
```

設定ファイルの`host`を到達不能なホスト（存在しないドメイン名など）に変更して再起動すると、赤LEDへの切り替わりとログへの記録を確認できる。
