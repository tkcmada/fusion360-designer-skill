# fusion360-designer-skill

Fusion 360 の **Python API** で、編集可能な履歴(スケッチ + 押し出し + 拘束 + パラメータ)を
持つパラメトリック部品を生成するためのスキル/規範集。build123d・STEP などの "履歴なしソリッド" を
Fusion ネイティブの編集可能設計へ起こし直す用途を想定。

## 構成
```
SKILL.md                          スキル定義(使う場面 / ワークフロー / ルール要約)
reference/
  rules.md                        設計ルール D1–D6 + 実装ルール I1–I10(詳細・根拠)
  cookbook.md                     Fusion API コードレシピ(params / sketch / 寸法 / projection /
                                  拘束 / ミラー・パターン / 押し出し / 配布)
examples/
  hat_mount_fusion/               実例: Raspberry Pi HAT (65×56.5) マウント
    hat_mount_fusion.py           スケッチ3枚(master_z0/bosses_mid/pilots_top)+押出3。
                                  D1(同一平面統合)/D2(projection)/D3(寸法)を実証。
    hat_mount_fusion.manifest
```

## コアルール
**設計**
- D0 ★ マスター(レイアウト)スケッチを設計の単一ソースに(駆動ジオメトリ=外形+全位置基準+主要寸法を1枚に集約、他はprojection)
- D1 1平面=1スケッチ。同一平面の形状は集約しプロファイル選択(seedスケッチを増やさない)(穴/切り欠きは内ループ、最大面積プロファイルで板を1押出)
- D2 平行平面へは master スケッチから projection(主要点/線を単一ソース化)
- D3 寸法を付与、主要値はユーザーパラメータにリンク
- D4 拘束で変化に追従(coincident/symmetric/equal/concentric…)
- D5 スケッチはフル拘束(自由度0・一意確定)
- D6 対称な穴/形状はミラー or パターン(個別に描かない)

**実装(Fusion API の要)**
- I1 rootComponent 直接(Part 単一コンポーネント制約)/ I2 ParametricDesignType
- I3 単位 内部cm・作図 mm×0.1・パラメータは `'65 mm'` / I4 `createByString('式')` でパラメータ駆動
- I5 開始オフセット `OffsetStartDefinition` / I6 Join/Cut は `participantBodies`
- I7 板は最大面積プロファイル / I8 projection + addCoincident
- I9 寸法/拘束/projection は try/except 保護 / I10 配布は `<name>/<name>.py` + `.manifest`

## 実行方法 (Fusion 360)
1. 新規 **Design** ドキュメントを開く。
2. ユーティリティ → **スクリプトとアドイン**(Shift+S)→ スクリプト → 「+」で
   `<name>` フォルダ(`.py` + `.manifest` 入り)を追加 → 実行。
3. タイムラインに スケッチ + 押し出し が並び、「修正 → パラメータを変更」で寸法編集 → 再構築。

