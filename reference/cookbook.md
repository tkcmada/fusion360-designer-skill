# Fusion 360 Python API クックブック

`SKILL.md` / `rules.md` の規範を実装するためのコードレシピ集。すべて mm 設計前提
(`MM = 0.1` で作図座標を cm へ)。寸法/拘束/projection は try/except 推奨(I9)。

## 0. ボイラープレート
```python
import adsk.core, adsk.fusion, traceback
MM = 0.1  # mm -> cm
HORIZ = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
VERT  = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Design ドキュメントを開いてから実行'); return
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType  # I2
        comp = design.rootComponent                                       # I1
        # ... build here ...
    except:
        if ui: ui.messageBox('失敗:\n{}'.format(traceback.format_exc()))
```

## 1. ユーザーパラメータ (I3/I4)
```python
up = design.userParameters
def P(name, val_mm):
    ex = up.itemByName(name)
    return ex if ex else up.add(name, adsk.core.ValueInput.createByString(f'{val_mm} mm'), 'mm', '')
P('BASE_T', 3.0); P('STANDOFF_H', 11.0)
def by(expr):  # パラメータ式 → ValueInput
    return adsk.core.ValueInput.createByString(expr)
```

## 2. 別平面へのスケッチ = ★押し出した「面」に直接スケッチ(オフセット平面を作らない)
前フィーチャの**先端面 (endFaces) に直接スケッチ**するのが第一選択。実ジオメトリに追従し
(寸法変更で面が動けばスケッチも動く)、構築平面が乱立しない。projection はその面スケッチ上で
そのまま機能し、他フィーチャの位置もカバーする。
```python
def top_face(feat):                       # 押し出しの先端面 (複数なら最上 z を選ぶ)
    faces = list(feat.endFaces)
    if not faces:                         # endFaces が無い形状は body 面から法線+Z で選別
        faces = [f for f in feat.bodies.item(0).faces]
    return max(faces, key=lambda f: f.centroid.z)
sk = comp.sketches.add(top_face(plate_extrude))   # 板の上面に直接スケッチ
# → ここに projection / 円 / 矩形を描き、上方向へ押し出す(別平面不要)
```
> 4 個の standoff 天面のように先端面が複数あっても、**1 面に sketch し projection で全位置を取得**すれば
> 1 スケッチで全数を扱える(面は無限平面として延びる)。

### 2b. フォールバック: オフセット構築平面(適切な面が無いときのみ)
```python
def offset_plane(comp, expr, name):
    pin = comp.constructionPlanes.createInput()
    pin.setByOffset(comp.xYConstructionPlane, by(expr))
    pl = comp.constructionPlanes.add(pin); pl.name = name
    return pl
plane_mid = offset_plane(comp, 'BASE_T', 'plane_mid')   # 面が存在しない初期段階等
```

## 3. 点 / 矩形 / 円
```python
def pt(x, y): return adsk.core.Point3D.create(x*MM, y*MM, 0)
sk = comp.sketches.add(comp.xYConstructionPlane); sk.name = 'master_z0'
rect = sk.sketchCurves.sketchLines.addCenterPointRectangle(pt(0,0), pt(L/2, W/2))  # 中心対称矩形
circ = sk.sketchCurves.sketchCircles.addByCenterRadius(pt(cx,cy), d/2*MM)
spt  = sk.sketchPoints.add(pt(cx,cy))   # projection 元の中心点
```
> `addCenterPointRectangle` は原点対称で描けるので D5(中心固定)に有利。

## 4. 寸法 (D3) — try/except で保護
```python
D = sk.sketchDimensions
def set_dim(dim, expr):
    try: dim.parameter.expression = expr
    except: pass
# 距離 (2点間)
try:
    set_dim(D.addDistanceDimension(p1, p2, HORIZ, adsk.core.Point3D.create(0, off, 0)), 'HAT_L + 2*MARGIN')
except: pass
# 直径
try:
    set_dim(D.addDiameterDimension(circ, pt(cx, cy+4)), 'FLANGE_HOLE_D')
except: pass
# 角度: D.addAngularDimension(line1, line2, textPoint)
```

## 5. projection (D2/I8)
```python
def project_point(target_sk, master_point):
    proj = target_sk.project(master_point)   # 参照ジオメトリを生成
    return proj.item(0)
ppt = project_point(sk_mid, master_center_point)
cc = sk_mid.sketchCurves.sketchCircles.addByCenterRadius(ppt.geometry, STANDOFF_D/2*MM)
try: sk_mid.geometricConstraints.addCoincident(cc.centerSketchPoint, ppt)  # 投影点に拘束
except: pass
```

## 6. 拘束 (D4/D5)
```python
gc = sk.geometricConstraints
gc.addCoincident(ptA, ptB)
gc.addHorizontal(line); gc.addVertical(line)
gc.addParallel(l1, l2); gc.addPerpendicular(l1, l2)
gc.addEqual(c1, c2)            # 半径/長さ等しい
gc.addConcentric(c1, c2)
gc.addSymmetry(entityA, entityB, symmetryLine)   # 対称拘束 (D6 のスケッチ版)
gc.addMidPoint(point, line)
# フル拘束の目安: sk.isFullyConstrained == True を確認
if not sk.isFullyConstrained:
    pass  # 不足拘束/寸法を追加
```

## 7. 対称 = 単一ソース駆動 (D1×D6)
> **まず D1**: 同一平面の対称は**スケッチ数を増やさず** 7a/7b で 1 スケッチ内に収める。
> フィーチャ mirror/pattern(7c/7d)は「別平面・別ボディの繰り返し」かつ seed が既存スケッチ由来のとき限定。

### 7a. 対称位置は「原点中心の構築矩形の四隅」で与える(推奨・D1 維持)
```python
# 中央寄せ構築矩形 (PITCH_X × PITCH_Y) → 四隅が対称な 4 点。穴/ボスの中心に流用。
rl = sk.sketchCurves.sketchLines
diag = rl.addCenterPointRectangle(pt(0,0), pt(PITCH_X/2, PITCH_Y/2))
for ln in diag: ln.isConstruction = True   # 構築線化
# 四隅(角点)を取得して穴中心に
corners = []
for ln in diag:
    for p in (ln.startSketchPoint, ln.endSketchPoint):
        if p not in corners: corners.append(p)
for cp in corners:
    c = sk.sketchCurves.sketchCircles.addByCenterRadius(cp.geometry, HOLE_D/2*MM)
    gc.addCoincident(c.centerSketchPoint, cp)   # 角点に拘束 → ピッチ変更に追従
# 構築矩形を寸法でパラメータ化すれば 4 穴が一括追従(対称は構築矩形が保証)
```

### 7b. スケッチ内 対称拘束(片側を描いて addSymmetry)
```python
gc.addSymmetry(circleftEntity, circRightEntity, yAxisConstructionLine)  # 1 スケッチ内で対称維持
```

### 7c. 矩形パターン(別平面/別ボディの繰り返しのみ)— seed は集約スケッチ由来
```python
pats = comp.features.rectangularPatternFeatures
ents = adsk.core.ObjectCollection.create(); ents.add(holeFeatureOrBody)
pin = pats.createInput(ents, comp.xConstructionAxis,
        adsk.core.ValueInput.createByReal(2), by('PI_PITCH_X'),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
pin.setDirectionTwo(comp.yConstructionAxis, adsk.core.ValueInput.createByReal(2), by('PI_PITCH_Y'))
pats.add(pin)   # 1穴 → 2×2 = 4穴 (ピッチはパラメータ駆動)
```
### 7d. フィーチャ・ミラー(対称面で複製、別ボディの繰り返し向け)
```python
mirs = comp.features.mirrorFeatures
ents = adsk.core.ObjectCollection.create(); ents.add(featureOrBody)
pin = mirs.createInput(ents, comp.xZConstructionPlane)   # XZ 面で Y 対称
mirs.add(pin)
```
> 同一平面の 4 穴は **7a(構築矩形の四隅)+ 内ループ**が D1 維持で最良。フィーチャパターン/ミラーは
> seed 用スケッチを増やしがち → **別平面/別ボディの繰り返し限定**で使う。

## 7.5. 集約スケッチからのプロファイル選択 (D1 — 1スケッチ→複数フィーチャ)
1 枚のスケッチに複数形状(板・穴・ボス・リブ…)を描き、**押し出しごとに必要プロファイルを選ぶ**。
これにより「機能ごとに seed スケッチを作る」を避けて D1 を守る。
```python
def profile_area(p):
    try: return p.areaProperties(adsk.fusion.CalculationAccuracy.LowCalculationAccuracy).area
    except: return 0.0
def largest(sk):                      # 板本体(穴/ノッチを除いた最大領域)
    return max(sk.profiles, key=profile_area, default=None)
def profile_containing(sk, x_mm, y_mm):   # 指定点を含むプロファイル(特定の穴/ボスを選ぶ)
    P = adsk.core.Point3D.create(x_mm*MM, y_mm*MM, 0)
    best, ba = None, -1.0
    for p in sk.profiles:
        try:
            bb = p.boundingBox
            if (bb.minPoint.x-1e-6 <= P.x <= bb.maxPoint.x+1e-6 and
                bb.minPoint.y-1e-6 <= P.y <= bb.maxPoint.y+1e-6):
                a = profile_area(p)
                if best is None or a < ba or ba < 0:  # 内側の小さい領域を優先
                    ba, best = a, p
        except: pass
    return best
def profiles_smaller_than(sk, area_threshold_cm2):  # 穴群(小領域)をまとめて選ぶ
    oc = adsk.core.ObjectCollection.create()
    for p in sk.profiles:
        if 0 < profile_area(p) < area_threshold_cm2: oc.add(p)
    return oc
```
使い分け:
- 板 = `largest(sk)` を NewBody 押し出し(穴/ノッチは内ループとして同時に開く)。
- 別平面のボス群 = その平面の 1 スケッチに全数描き、`all_profiles(sk)` を Join で一括押し出し。
- 個別フィーチャ化が要る時のみ `profile_containing()` で seed を選び、必要なら 7c/7d でパターン/ミラー。

## 8. 押し出し (I5/I6/I7)
```python
exts = comp.features.extrudeFeatures
def all_profiles(sk):
    oc = adsk.core.ObjectCollection.create()
    for p in sk.profiles: oc.add(p)
    return oc
def largest_profile(sk):  # 穴/ノッチ込みスケッチの板本体 (I7)
    best, ba = None, -1.0
    for p in sk.profiles:
        try: a = p.areaProperties(adsk.fusion.CalculationAccuracy.LowCalculationAccuracy).area
        except: a = 0
        if a > ba: ba, best = a, p
    return best

# NewBody (板)
ei = exts.createInput(largest_profile(skM), adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
ei.setDistanceExtent(False, by('BASE_T'))
body = exts.add(ei).bodies.item(0); body.name = 'part'

# Join (別平面から立ち上げ + 既存ボディへ結合)
ei = exts.createInput(all_profiles(skB), adsk.fusion.FeatureOperations.JoinFeatureOperation)
ei.startExtent = adsk.fusion.OffsetStartDefinition.create(by('BASE_T'))   # I5
ei.setDistanceExtent(False, by('STANDOFF_H'))
ei.participantBodies = [body]                                             # I6
exts.add(ei)

# Cut (上面から下穴)
ei = exts.createInput(all_profiles(skP), adsk.fusion.FeatureOperations.CutFeatureOperation)
ei.setDistanceExtent(False, by('-SCREW_DEPTH'))   # 負値で逆向き
ei.participantBodies = [body]
exts.add(ei)
```

## 9. フィレット / 面取り(任意, try/except)
```python
try:
    fil = comp.features.filletFeatures
    edges = adsk.core.ObjectCollection.create()
    # edges.add(...選択した縦エッジ...)
    fin = fil.createSimpleInput(edges); fin.addConstantRadiusEdgeSet(edges, by('R'), True)
    fil.add(fin)
except: pass
```

## 10. 配布 (I10)
```
<name>/<name>.py
<name>/<name>.manifest
```
manifest 例:
```json
{ "autodeskProduct": "Fusion360", "type": "script",
  "supportedOS": "windows|mac", "editEnabled": true,
  "description": { "": "..." } }
```
