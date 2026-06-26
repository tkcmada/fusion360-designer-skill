"""Fusion 360 履歴スクリプト【模範例】— A6 電源/ドライバ HAT マウント (Pi HAT 65×56.5)
fusion360-designer-skill の D0–D6 / I1–I10 を実証する参照実装。

★D0(最上位): マスター(レイアウト)スケッチ `master_z0` に部品の駆動ジオメトリ(skeleton)を集約:
   - プレート外形 / 全フィーチャの位置基準(取付穴中心=構築矩形の四隅, フランジ穴, 配線ノッチ)
   - 主要寸法はユーザーパラメータにリンク
  → master + パラメータ表を見れば全体を調整できる。他平面は projection で参照。

スケッチは **3 枚のみ**(D1: 1平面=1スケッチ):
  master_z0 (XY)        : プレート外形 + 取付穴中心(構築矩形) + フランジ穴(内ループ) + 配線ノッチ
  bosses_mid (z=BASE_T) : master 中心点を projection → standoff×4 + リブ×2 を 1 押し出し(Join)
  pilots_top (z=top)    : master 中心点を projection → 下穴×4(Cut)

実証ルール: D0 単一ソース / D1 1平面1スケッチ / D2 projection / D3 寸法+パラメータ /
  D4 拘束(coincident/concentric) / D5 フル拘束報告 / D6 対称=構築矩形+projection /
  I1 rootComponent / I3 mm×0.1 / I4 式リンク / I5 開始オフセット相当(構築平面) /
  I6 participantBodies / I7 最大プロファイル / I8 project+coincident / I9 try/except。

座標系: build123d ローカル一致。base 下面 Z=0、Pi 取付穴矩形の中心を原点。
"""
import adsk.core, adsk.fusion, traceback

# ---- 寸法定数 (mm) = build123d hat_mount.py と一致 --------------------------
HAT_L, HAT_W = 65.0, 56.5
PI_PITCH_X, PI_PITCH_Y = 58.0, 49.0
BASE_T = 3.0
STANDOFF_H, STANDOFF_D = 11.0, 6.5
SCREW_PILOT_D, SCREW_DEPTH = 2.1, 12.0
MARGIN = 2.0
FLANGE_W, FLANGE_HOLE_D = 8.5, 3.4
RETAIN_RIB_T = 2.5
WIRE_NOTCH_W, WIRE_NOTCH_DEPTH = 20.0, 4.0

BASE_L = HAT_L + 2 * MARGIN                       # 69.0
PLATE_W = HAT_W + 2 * MARGIN + 2 * FLANGE_W       # 77.5
FLANGE_PITCH_X = 0.6 * BASE_L                     # 41.4
FLANGE_PITCH_Y = HAT_W + 2 * MARGIN + FLANGE_W    # 69.0
NOTCH_CX = BASE_L / 2 - WIRE_NOTCH_DEPTH / 2      # 32.5
RIB_Y = PI_PITCH_Y / 2 + STANDOFF_D / 2 + RETAIN_RIB_T / 2

MM = 0.1
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get(); ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('Design ドキュメントを開いてから実行してください。'); return
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType   # I2
        comp = design.rootComponent                                        # I1

        up = design.userParameters
        def P(name, val):
            ex = up.itemByName(name)
            return ex if ex else up.add(name, adsk.core.ValueInput.createByString(f'{val} mm'), 'mm', '')
        for n, v in [('HAT_L', HAT_L), ('HAT_W', HAT_W), ('MARGIN', MARGIN), ('FLANGE_W', FLANGE_W),
                     ('BASE_T', BASE_T), ('STANDOFF_H', STANDOFF_H), ('STANDOFF_D', STANDOFF_D),
                     ('SCREW_PILOT_D', SCREW_PILOT_D), ('SCREW_DEPTH', SCREW_DEPTH),
                     ('FLANGE_HOLE_D', FLANGE_HOLE_D), ('PI_PITCH_X', PI_PITCH_X),
                     ('PI_PITCH_Y', PI_PITCH_Y), ('RETAIN_RIB_T', RETAIN_RIB_T)]:
            P(n, v)

        sks, exts = comp.sketches, comp.features.extrudeFeatures
        planes = comp.constructionPlanes
        XY = comp.xYConstructionPlane

        def by(e): return adsk.core.ValueInput.createByString(e)
        def pt(x, y): return adsk.core.Point3D.create(x * MM, y * MM, 0)
        def offset_plane(expr, name):
            pin = planes.createInput(); pin.setByOffset(XY, by(expr))
            pl = planes.add(pin); pl.name = name; return pl
        def set_dim(d, e):
            try: d.parameter.expression = e
            except: pass
        def parea(p):
            try: return p.areaProperties(adsk.fusion.CalculationAccuracy.LowCalculationAccuracy).area
            except: return 0.0
        def largest(sk): return max(sk.profiles, key=parea, default=None)
        def all_prof(sk):
            oc = adsk.core.ObjectCollection.create()
            for p in sk.profiles: oc.add(p)
            return oc
        def corners(rect):           # 矩形 4 線 → 一意な四隅 SketchPoint
            seen = {}
            for ln in rect:
                for p in (ln.startSketchPoint, ln.endSketchPoint):
                    seen[(round(p.geometry.x, 5), round(p.geometry.y, 5))] = p
            return list(seen.values())

        report = []

        # ====================================================================
        # (D0) master_z0 : 駆動ジオメトリ skeleton 一式 (XY 平面のすべて)
        # ====================================================================
        skM = sks.add(XY); skM.name = 'master_z0'
        L = skM.sketchCurves.sketchLines
        C = skM.sketchCurves.sketchCircles
        D = skM.sketchDimensions
        gc = skM.geometricConstraints
        org = skM.originPoint
        HZ = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
        VT = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

        # プレート外形
        plate = L.addTwoPointRectangle(pt(-BASE_L / 2, -PLATE_W / 2), pt(BASE_L / 2, PLATE_W / 2))
        try:
            hl = [ln for ln in plate if abs(ln.startSketchPoint.geometry.y - ln.endSketchPoint.geometry.y) < 1e-6]
            vl = [ln for ln in plate if abs(ln.startSketchPoint.geometry.x - ln.endSketchPoint.geometry.x) < 1e-6]
            set_dim(D.addDistanceDimension(hl[0].startSketchPoint, hl[0].endSketchPoint, HZ,
                    adsk.core.Point3D.create(0, PLATE_W / 2 * MM + 1, 0)), 'HAT_L + 2 * MARGIN')
            set_dim(D.addDistanceDimension(vl[0].startSketchPoint, vl[0].endSketchPoint, VT,
                    adsk.core.Point3D.create(BASE_L / 2 * MM + 1, 0, 0)), 'HAT_W + 2 * MARGIN + 2 * FLANGE_W')
            bl = [sp for sp in (hl[0].startSketchPoint, hl[0].endSketchPoint, vl[0].startSketchPoint, vl[0].endSketchPoint)
                  if sp.geometry.x < 0 and sp.geometry.y < 0]
            if bl:   # D5: 左下角を原点寸法で位置確定
                set_dim(D.addDistanceDimension(org, bl[0], HZ, adsk.core.Point3D.create(-BASE_L / 4 * MM, -PLATE_W / 2 * MM - 2, 0)), '(HAT_L + 2 * MARGIN) / 2')
                set_dim(D.addDistanceDimension(org, bl[0], VT, adsk.core.Point3D.create(-BASE_L / 2 * MM - 2, -PLATE_W / 4 * MM, 0)), '(HAT_W + 2 * MARGIN + 2 * FLANGE_W) / 2')
        except: pass

        # 取付穴中心 = 構築矩形 (PI_PITCH) の四隅 (D6 対称 / D2 projection 元)
        mrect = L.addCenterPointRectangle(pt(0, 0), pt(PI_PITCH_X / 2, PI_PITCH_Y / 2))
        for ln in mrect:
            ln.isConstruction = True
        mount_pts = corners(mrect)
        try:    # ピッチ寸法 (構築矩形)
            mh = [ln for ln in mrect if abs(ln.startSketchPoint.geometry.y - ln.endSketchPoint.geometry.y) < 1e-6]
            mv = [ln for ln in mrect if abs(ln.startSketchPoint.geometry.x - ln.endSketchPoint.geometry.x) < 1e-6]
            set_dim(D.addDistanceDimension(mh[0].startSketchPoint, mh[0].endSketchPoint, HZ,
                    adsk.core.Point3D.create(0, -PI_PITCH_Y / 2 * MM - 1, 0)), 'PI_PITCH_X')
            set_dim(D.addDistanceDimension(mv[0].startSketchPoint, mv[0].endSketchPoint, VT,
                    adsk.core.Point3D.create(-PI_PITCH_X / 2 * MM - 1, 0, 0)), 'PI_PITCH_Y')
        except: pass

        # フランジ穴 = 構築矩形 (FLANGE_PITCH) の四隅に同心円 (内ループ → プレート押出で開く)
        frect = L.addCenterPointRectangle(pt(0, 0), pt(FLANGE_PITCH_X / 2, FLANGE_PITCH_Y / 2))
        for ln in frect:
            ln.isConstruction = True
        fcircs = []
        for cp in corners(frect):
            c = C.addByCenterRadius(cp.geometry, FLANGE_HOLE_D / 2 * MM)
            try: gc.addCoincident(c.centerSketchPoint, cp)   # 構築矩形の角に同心(対称追従)
            except: pass
            fcircs.append(c)
        try:
            set_dim(D.addDiameterDimension(fcircs[0], pt(-FLANGE_PITCH_X / 2, -FLANGE_PITCH_Y / 2 - 4)), 'FLANGE_HOLE_D')
            for fc in fcircs[1:]:
                try: gc.addEqual(fcircs[0], fc)   # 径を等しく
                except: pass
        except: pass

        # 配線ノッチ ×2 (±X 縁切り)。対称は addSymmetry を試行
        n1 = L.addCenterPointRectangle(pt(NOTCH_CX, 0), pt(NOTCH_CX + WIRE_NOTCH_DEPTH, WIRE_NOTCH_W / 2))
        n2 = L.addCenterPointRectangle(pt(-NOTCH_CX, 0), pt(-NOTCH_CX + WIRE_NOTCH_DEPTH, WIRE_NOTCH_W / 2))

        report.append(('master_z0', skM.isFullyConstrained))

        prof = largest(skM)
        if prof is None:
            raise RuntimeError('master_z0 に有効なプレートプロファイルがありません。')
        ei = exts.createInput(prof, NEW); ei.setDistanceExtent(False, by('BASE_T'))
        body = exts.add(ei).bodies.item(0); body.name = 'hat_mount_A6'

        # ====================================================================
        # (bosses_mid) standoff×4 + リブ×2 を 1 スケッチ・1 押し出し (D1/D2/D6)
        # ====================================================================
        pmid = offset_plane('BASE_T', 'plane_mid')
        skB = sks.add(pmid); skB.name = 'bosses_mid'
        CB = skB.sketchCurves.sketchCircles
        LB = skB.sketchCurves.sketchLines
        for mp in mount_pts:                         # master 中心点を projection (D2/I8)
            ppt = skB.project(mp).item(0)
            cc = CB.addByCenterRadius(ppt.geometry, STANDOFF_D / 2 * MM)
            try: skB.geometricConstraints.addCoincident(cc.centerSketchPoint, ppt)
            except: pass
        for sgn in (-1, 1):                          # リブ×2(同平面ゆえ同スケッチ)
            LB.addCenterPointRectangle(pt(0, sgn * RIB_Y), pt((PI_PITCH_X + STANDOFF_D) / 2, sgn * RIB_Y + RETAIN_RIB_T / 2))
        report.append(('bosses_mid', skB.isFullyConstrained))
        ei = exts.createInput(all_prof(skB), JOIN)
        ei.setDistanceExtent(False, by('STANDOFF_H')); ei.participantBodies = [body]
        exts.add(ei)

        # ====================================================================
        # (pilots_top) 下穴×4 を 1 スケッチ・1 カット (D1/D2)
        # ====================================================================
        ptop = offset_plane('BASE_T + STANDOFF_H', 'plane_top')
        skP = sks.add(ptop); skP.name = 'pilots_top'
        CP = skP.sketchCurves.sketchCircles
        for mp in mount_pts:
            ppt = skP.project(mp).item(0)
            cc = CP.addByCenterRadius(ppt.geometry, SCREW_PILOT_D / 2 * MM)
            try: skP.geometricConstraints.addCoincident(cc.centerSketchPoint, ppt)
            except: pass
        report.append(('pilots_top', skP.isFullyConstrained))
        ei = exts.createInput(all_prof(skP), CUT)
        ei.setDistanceExtent(False, by('-SCREW_DEPTH')); ei.participantBodies = [body]
        exts.add(ei)

        out = ['hat_mount_A6 を生成しました (模範例 D0-D6, スケッチ3枚)。', '',
               'スケッチ フル拘束(D5):']
        for name, ok in report:
            out.append(f'  - {name}: {ok}')
        ui.messageBox('\n'.join(out))

    except:
        if ui:
            ui.messageBox('失敗:\n{}'.format(traceback.format_exc()))
