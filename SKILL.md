---
name: fusion360-designer
description: >-
  Generate parametric Fusion 360 models with the Python API (sketch + extrude
  history), following clean parametric-CAD conventions. Use when writing/editing
  Fusion 360 design scripts, converting build123d / STEP parts into an editable
  Fusion timeline, or applying Fusion sketch/constraint/dimension best-practices.
  Triggers: "fusion script", "fusion 360 python", "fusion 履歴スクリプト",
  "parametric fusion", "sketch+extrude script".
---

# Fusion 360 Designer Skill

Fusion 360 の **Python API** で、編集可能な履歴(タイムライン = スケッチ + 押し出し +
拘束 + パラメータ)を持つパラメトリック部品を生成するためのスキル。
build123d / STEP で作った "履歴なしソリッド" を、Fusion ネイティブの **編集可能な設計**に
起こし直す用途を想定。

## このスキルを使う場面
- Fusion 360 で「スケッチ+押し出し」の履歴付き部品を **スクリプト生成**したいとき。
- build123d / STEP 部品を Fusion の編集可能モデルへ移植したいとき。
- Fusion のスケッチ/拘束/寸法/ミラー/パターンの作法に沿って設計したいとき。

## 進め方 (ワークフロー)
1. **入力を読む**: build123d コード or 図面 or 寸法表。部品の「平面ごとの形状」と
   「対称性」「主要寸法(パラメータ化したい値)」を洗い出す。
2. **平面で分類**: 形状を押し出し平面ごとにグルーピング。同一平面=1スケッチに統合、
   平行平面=master スケッチから projection、と決める([reference/rules.md](reference/rules.md) D1/D2)。
3. **master スケッチ設計**: 主要点/線/輪郭を1枚に集約。**拘束 + 寸法 + 角度でフル拘束**にし、
   **対称はミラー/パターン**で表現(D4/D5/D6)。主要寸法はユーザーパラメータにリンク(D3)。
4. **API で実装**: [reference/cookbook.md](reference/cookbook.md) のレシピを使う。
   実装上の落とし穴は [reference/rules.md](reference/rules.md) の I1–I10 を必ず踏襲。
5. **配布形式**: `<name>/<name>.py` + `<name>/<name>.manifest`(3名一致)で zip(I10)。
6. **検証**: Fusion で実行 → タイムライン/フル拘束/パラメータ編集を確認。エラーは API 差異を
   修正(寸法/projection/拘束は try/except で保護してあるので形状は残る)。

## ルール (要約 — 詳細は reference/rules.md)
**設計**
- **D0 ★最上位** マスター(レイアウト)スケッチを **設計の単一ソース**にする。駆動ジオメトリ(外形 +
  全フィーチャの位置基準 + 主要寸法)を 1 枚に集約し、他は projection/参照。"全部1スケッチ"は不可
  (多平面)ゆえ「**X/Y skeleton を master + 高さ等はパラメータ + 別平面は projection**」。
  → スケッチを開かずマスター+パラメータ表で全体を調整できる状態にする。D1/D2/D6 は D0 の実現手段。
- **D1** 1平面=1スケッチ(厳守)。同一平面の全形状を1スケッチに集約し、押し出しごとにプロファイル選択(seedスケッチを乱立させない)。
- **D2** 平行平面へは **master スケッチから projection**(主要点/線を単一ソース化)。
- **D3** スケッチに **寸法を付与**、主要値は **ユーザーパラメータにリンク**。
- **D4** **拘束**を使い変化に追従(coincident / horizontal / vertical / parallel / equal / symmetric / concentric …)。
- **D5** スケッチは **フル拘束(自由度0・一意確定)**。未拘束を残さない。
- **D6** 対称な穴/形状は **ミラー or パターン**(個別に描かない)。

**実装 (Fusion API)**
- **I1** `design.rootComponent` に直接モデリング(Part 単一コンポーネント制約、`addNewComponent` 不可)。
- **I2** `design.designType = ParametricDesignType`。
- **I3** 単位: 内部 cm。作図 = mm×0.1。寸法パラメータは `'65 mm'` 文字列。
- **I4** パラメータリンク = `ValueInput.createByString('BASE_T')` / 式。
- **I5** 開始オフセット = `OffsetStartDefinition.create(by('BASE_T'))`。
- **I6** Join/Cut は `participantBodies=[body]`。
- **I7** 板は **最大面積プロファイル**を選ぶ。
- **I8** projection = `target.project(master_point)` → 投影点に同心 + `addCoincident`。
- **I9** 寸法/拘束/projection は **try/except** で保護。
- **I10** 配布 = `<name>/<name>.py` + `.manifest`(同名)。

## 機構検証 (r1–r3) — 設計を「動く・干渉しない・固定される」まで証明する
オーサリング (上記 D/I) は *編集可能な* モデルを作る。**機構検証**は *その機構が正しい* ことを証明する。
弱い検証 (bbox/中立姿勢のみ/目視/仮定/pass 盲信) を正しさの証明にせず、実ジオメトリの強検証へ:
- **r1** 全ペアが干渉しない / **r2** 駆動源から可動域いっぱいで駆動でき各姿勢で干渉しない / **r3** 宙に浮かず固定。
- 干渉は必ず **boolean 交差体積** `(a&b).volume`(bbox 厳禁)、可動は **可動域端までスイープ**、固定は **接触/締結を証明**。
- 「干渉ゼロ・接触あり」の静的共存だけでなく **機能幾何**(伝達方向 / 保持 / 製造一体性 / 締結 / 閉じた穴・荷重経路) を検査。
- **二重ループ**: 内側=決定論ハーネス / 外側=独立レビュー(r1–r3 と成果物のみ渡し、whitelist/意図は渡さない)。
- 完了前に必ずハーネスを全 green にする。詳細・コードは reference を参照。

## 参考
- [reference/rules.md](reference/rules.md) — 設計 D1–D6 / 実装 I1–I10(詳細・根拠)
- [reference/cookbook.md](reference/cookbook.md) — Fusion API コードレシピ
- [reference/verification.md](reference/verification.md) — 機構検証 r1–r3 / P1–P6 / 機能幾何 / 二重ループ
- [reference/verification-harness.md](reference/verification-harness.md) — 実行ハーネス(実体ブール積/スイープ/固定/リンケージ) + 検査タクソノミ
- [examples/hat_mount_fusion/](examples/hat_mount_fusion/) — 実例(HAT マウント、D1/D2/D3 実証)
