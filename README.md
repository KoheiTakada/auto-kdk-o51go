# Auto-KDK o51go

このリポジトリは、キーボード自動設計ツール [Auto-KDK](https://github.com/sekigon-gonnoc/auto-kdk) を使用して生成された **o51go** ライクなキーボードの設計データを管理するプロジェクトです。

サリチル酸氏による [o51go](https://salicylic-acid3.hatenablog.com/entry/go40keeb-build-guide) のレイアウト/コンセプトをベースに、Auto-KDKを用いてPCB、ケース、ファームウェア設定を生成しています。

## 📂 概要 (Overview)

Auto-KDKのパラメータ設定により、以下のデータを自動生成・管理しています。

* **PCB設計データ**: KiCadプロジェクトおよび製造用ガーバーデータ
* **ケースデータ**: 3Dプリント用のSTL/STEPファイル
* **ファームウェア**: Vial / QMK / ZMK 用の設定ファイル

## 🚀 使い方 (Usage)

### 1. 設計の調整
リポジトリ内の `configs/layout.json` (または該当する設定ファイル) を [Auto-KDK Web App](https://github.com/sekigon-gonnoc/auto-kdk) にロードすることで、Webブラウザ上で形状や配線の再設定が可能です。

### 2. PCBの製造
`pcb/gerbers/` ディレクトリ内のZIPファイルを [JLCPCB](https://jlcpcb.com/) 等の基板製造メーカーにアップロードしてください。

### 3. ケースの作成
`case/` ディレクトリ内のSTLファイルを3Dプリンターで出力 もしくはJLC3DPに発注してください。Bambulab A1で出力可能なサイズです。

### 4. ファームウェア
`firmware/` ディレクトリを参照し、コントローラー（Auto-KDK Controller Board）にファームウェアを書き込んでください。

## 🛠️ ディレクトリ構成

```text
.
├── configs/       # Auto-KDK用の入力設定ファイル (.json)
├── pcb/           # KiCadプロジェクトおよび製造データ
│   └── gerbers/   # そのまま発注可能なZIPファイル
├── case/          # 3Dモデルデータ (STL/STEP)
├── firmware/      # ファームウェア設定 (vial.json, keymap等)
└── README.md      # 本ファイル
```

## 🤝 Credits & Acknowledgements
巨人の肩に乗りまくっています。
- Original o51go Concept: Designed by Salicylic_acid3
- Auto-KDK: Developed by sekigon-gonnoc

Note: This is an unofficial derivative project using Auto-KDK. Please do not contact the original designers for support regarding this specific repository.
