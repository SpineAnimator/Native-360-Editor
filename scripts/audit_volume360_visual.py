#!/usr/bin/env python3
"""Fail-closed pixel audit of PNGs rendered by the REAL licensed Spine 4.3 Editor.

Does not generate animation or infer artistic approval. Catches the specific
cherry-360 regressions where the rear is rectangular or overexposed flat red.
"""
import argparse
import json
from pathlib import Path
import re
from collections import Counter
from PIL import Image

def red(r,g,b,a):
    return a>=120 and r>=175 and g<=130 and r>g*1.8 and r>b*1.35

def pixels(image):
    im=image.convert("RGBA")
    return im.width,im.height,list(im.getdata())

def row_runs(mask,width,height):
    return [max((len(part) for part in "".join("1" if mask[y*width+x] else "0" for x in range(width)).split("0")),default=0)
            for y in range(height)]

def lower_fruit_side_gold(image):
    """Measure golden interior cavities from THIS frame's berry, not 0° halo.

    This is a passive visual diagnostic on genuine Spine Editor PNGs.
    No source PSD texels or animation are ever created or modified.
    """
    w,h,data=pixels(image)
    fruit=[i for i,p in enumerate(data) if red(*p)]
    if len(fruit)<100:
        raise ValueError("No red fruit available for side-hole measurement")
    xs=[i%w for i in fruit];ys=[i//w for i in fruit]
    x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
    lower=y0+(y1-y0)//2
    reds=gold=dark=warm=0
    brown_palette=Counter()
    flat_hot_palette=Counter()
    red_channel_palette=Counter()
    # 7.2%-width incorrectly missed the realistic 36px enclosed triangular
    # cavity at 192px. A wider 11% catchment catches both edges, while an
    # independent warm-red colour gate excludes normal purple background gaps.
    max_horizontal=max(8,int(w*.11))
    # Only count DARK RED/BROWN material pockets bounded by berry pigment
    # on BOTH sides, never ordinary purple source background between fruits.
    for y in range(lower,y1+1):
        row_is_red=[red(*data[y*w+x]) for x in range(w)]
        left=[w+1]*w;right=[w+1]*w
        last=-w
        for x in range(w):
            if row_is_red[x]:last=x
            left[x]=x-last
        last=2*w
        for x in range(w-1,-1,-1):
            if row_is_red[x]:last=x
            right[x]=last-x
        for x in range(x0,x1+1):
            r,g,b,a=data[y*w+x]
            if row_is_red[x]:reds+=1
            # Detect a broad constant red CHANNEL, not only repeated exact RGB.
            # A flat side can vary G/B slightly yet clamp thousands of texels
            # to the same red floor (R=145 in licensed run 43018228841).
            if a>=120 and r>=100 and r>g*1.3 and r>b*1.12:
                red_channel_palette[r]+=1
            # Licensed Editor PR123 produced a visually hollow 3D fruit side
            # after near-black/gold texels had been recoloured into a flat
            # mud-brown rectangle. Repeated identical brown texels on a red
            # return-side fruit are material collapse, not source detail.
            # Do not classify ordinary burgundy shading, purple background,
            # or original PSD setup as automatically defective.
            if (a>=120 and 105<=r<=175 and 23<=g<=100 and b<=85
                    and r>g*1.3 and g>r*.19 and g<r*.63):
                brown_palette[(r,g,b)]+=1
            # Source-relative repeated hot-red pixels reveal a stretched flat
            # colour triangle when a warm crease was recoloured into bright
            # flesh (native PR123 40-frame SHA 074c00, frames 26–29).
            # Genuine front PSD has at most 3 identical hot-colour pixels;
            # the defective side repeats RGB(246,73,67) 22–26 times.
            if (a>=120 and r>=215 and 25<=g<=125 and 10<=b<=130
                    and r>g*1.8 and r>b*1.7):
                flat_hot_palette[(r,g,b)]+=1
            if a>=120 and r>=175 and g>=110 and b<=135 and g>b*1.20:
                gold+=1
            if (a>=120 and r>=105 and 30<=g<=155 and b<110 and
                    r>g*1.20 and g>b*1.25):
                warm+=1
            if (a>=120 and 38<=r<110 and g<100 and b<100 and
                r>g*1.25 and r>b*1.15 and
                0<left[x]<=max_horizontal and
                0<right[x]<=max_horizontal):
                dark+=1
    common=brown_palette.most_common(1)
    mode_rgb,mode_count=common[0] if common else (None,0)
    hot_common=flat_hot_palette.most_common(1)
    hot_rgb,hot_count=hot_common[0] if hot_common else (None,0)
    red_mode=red_channel_palette.most_common(1)
    red_mode_r,red_mode_count=red_mode[0] if red_mode else (None,0)
    red_mode_support=sum(red_channel_palette.values())
    return {"lowerFruitRedPixels":reds,"lowerFruitGoldPixels":gold,
            "lowerFruitGoldFraction":round(gold/max(reds,1),6),
            "lowerFruitDarkPixels":dark,
            "lowerFruitDarkFraction":round(dark/max(reds,1),6),
            "lowerFruitWarmPixels":warm,
            "lowerFruitWarmFraction":round(warm/max(reds,1),6),
            "brownFlatModePixels":mode_count,
            "brownFlatModeRGB":list(mode_rgb) if mode_rgb else None,
            "brownFlatModeFraction":round(mode_count/max(reds,1),6),
            "hotRedFlatModePixels":hot_count,
            "hotRedFlatModeRGB":list(hot_rgb) if hot_rgb else None,
            "redChannelModeValue":red_mode_r,
            "redChannelModePixels":red_mode_count,
            "redChannelSupportPixels":red_mode_support,
            "redChannelModeFraction":round(red_mode_count/max(1,red_mode_support),6)}


def audit(frames):
    if len(frames)<30:
        raise ValueError("Official Editor 360 render needs at least 30 consecutive frames")
    order=[]
    for frame in frames:
        match=re.search(r"(\d+)\.png$",frame.name)
        if not match:
            raise ValueError("Unnumbered Editor animation frame")
        order.append((int(match.group(1)),frame))
    order.sort()
    if [idx for idx,_ in order]!=list(range(len(order))):
        raise ValueError("Missing or repeated full-animation frame")
    first,final=Image.open(order[0][1]),Image.open(order[-1][1])
    w,h,front=pixels(first)
    w2,h2,ending=pixels(final)
    if (w,h)!=(w2,h2) or front!=ending:
        raise ValueError("Original 0-degree PSD art did not return exactly at 360 degrees")
    # Fruit is the red subject below the stem. Relative coordinates avoid
    # dependence on one particular source-image resolution.
    sample=[(x,y) for y in range(int(h*.48),h) for x in range(w)
            if red(*front[y*w+x])]
    if len(sample)<100:
        raise ValueError("No independently measurable red fruit in source frame")
    xs=[x for x,_ in sample];ys=[y for _,y in sample]
    x0,x1=max(0,min(xs)-2),min(w-1,max(xs)+2)
    y0,y1=max(0,min(ys)-2),min(h-1,max(ys)+2)
    width,height=x1-x0+1,y1-y0+1
    def inspect(image):
        wi,he,data=pixels(image)
        if (wi,he)!=(w,h):
            raise ValueError("Frame sizes differ; cannot compare source and rear")
        sample_pixels=[data[y*w+x] for y in range(y0,y1+1)
                       for x in range(x0,x1+1)]
        mask=[red(*pixel) for pixel in sample_pixels]
        total=sum(mask)
        clipped=sum(pixel[0]>=248 for pixel,valid in zip(sample_pixels,mask) if valid)
        clipped_fraction=round(clipped/max(total,1),4)
        runs=row_runs(mask,width,height)
        # This catches the actual smooth red plates that survived the rectangle
        # and clipping audit in the licensed 40-frame Spine 4.3.26 render:
        # compare neighbouring red texels on both axes only when both texels
        # belong to the cherry. Do not count antialiased boundaries or backdrop.
        detail=0
        adjacency=0
        for yy in range(height):
            for xx in range(width):
                i=yy*width+xx
                if not mask[i]:
                    continue
                if xx and mask[i-1]:
                    detail+=abs(sample_pixels[i][0]-sample_pixels[i-1][0])
                    adjacency+=1
                if yy and mask[i-width]:
                    detail+=abs(sample_pixels[i][0]-sample_pixels[i-width][0])
                    adjacency+=1
        red_detail=round(detail/max(1,adjacency),4)
        # A near-black cavity can survive a generic dark-pixel gate when
        # the turning cherry gets edge-on and fewer red pixels remain.
        # Count only dark texels with close red fruit on BOTH sides of the
        # SAME row. This avoids counting purple backdrop as a hollow fruit.
        radius=max(7,min(16,round(width*.08)))
        lower_red_support=0
        dark_bridge_pixels=0
        for yy in range(int(height*.43),height):
            start=yy*width
            row=mask[start:start+width]
            positions=[xx for xx,hit in enumerate(row) if hit]
            if not positions:
                continue
            lower_red_support+=len(positions)
            if positions[-1]-positions[0]<max(20,width*.18):
                continue
            for xx in range(positions[0]+1,positions[-1]):
                r,g,b,a=sample_pixels[start+xx]
                if a<120 or r>=105 or g>=105 or b>=105:
                    continue
                left=row[max(positions[0],xx-radius):xx]
                right=row[xx+1:min(positions[-1]+1,xx+radius+1)]
                if any(left) and any(right):
                    dark_bridge_pixels+=1
        dark_bridge_fraction=round(dark_bridge_pixels/max(1,lower_red_support),6)
        # A genuine Editor 4.3.26 360 render can expose a bright triangular
        # material hole just below the source fruit silhouette. Check a
        # source-relative lower-body area, including a bounded extra margin.
        gold=0
        lower_y=y0+int(height*.53)
        bottom_y=min(h,y1+max(12,int(height*.24))+1)
        for yy in range(lower_y,bottom_y):
            for xx in range(x0,x1+1):
                r,g,b,a=data[yy*w+xx]
                if a>=120 and r>=225 and g>=145 and b<=110:
                    gold+=1
        gold_fraction=round(gold/max(total,1),6)
        # A wide solid rectangle in >=12 rows is a source-geometry failure,
        # not a valid sphere or cherry silhouette.
        plate=sum(run>=width*.68 for run in runs)
        return {"redPixels":total,"longHorizontalRows":plate,"maxRun":max(runs),
                "clippedRedFraction":clipped_fraction,
                "redLocalDetail":red_detail,"redDetailPairs":adjacency,
                "lowerFruitGoldPixels":gold,"lowerFruitGoldToRedFraction":gold_fraction,
                "lowerRedSupportPixels":lower_red_support,
                "darkBridgePixels":dark_bridge_pixels,
                "darkBridgeFraction":dark_bridge_fraction}
    baseline=inspect(first)
    begin=int(len(order)*.44);end=int(len(order)*.59)+1
    backs=[{"frame":i,**inspect(Image.open(order[i][1]))} for i in range(begin,end)]
    failures=[m for m in backs
              if m["longHorizontalRows"]>=12 and
                 (m["redPixels"]>baseline["redPixels"]*1.12 or
                  m["longHorizontalRows"]>baseline["longHorizontalRows"]+11)]
    # A rear surface with most cherry pixels pinned at R=255 is a
    # material regression even if its silhouette no longer looks rectangular.
    # Compare to the exact original 0-degree PSD frame and require a generous
    # absolute threshold to avoid mistaking a small highlight for a failure.
    clipping_limit=max(.43,baseline["clippedRedFraction"]+.24)
    overexposed=[m for m in backs
                 if m["redPixels"]>=max(120,baseline["redPixels"]*.45)
                 and m["clippedRedFraction"]>clipping_limit]
    # Low-frequency colour on inferred backs can look like a smooth, flat
    # red plastic plate while passing rectangle and R=255 clipping gates.
    # This conservative guard rejects only sustained loss of original fruit
    # detail over several full-coverage rear frames. It is not art approval.
    detail_limit=round(baseline["redLocalDetail"]*.57,4)
    low_detail=[m for m in backs if
                m["redPixels"]>=max(600,baseline["redPixels"]*.70)
                and m["redDetailPairs"]>=500
                and m["redLocalDetail"]<detail_limit]
    sustained_low_detail=len(low_detail)>=3
    # The old gate reported PASS for frames 26/27 with severe visible lower
    # fruit holes. Require sustained, consecutive bright-gold bursts on the
    # returning side; expose earlier-side anomalies for review without a
    # speculative automatic art verdict.
    first_side=[]
    for i in range(int(len(order)*.34),int(len(order)*.45)):
        with Image.open(order[i][1]) as frame:
            first_side.append({"frame":i,**inspect(frame),
                               **lower_fruit_side_gold(frame)})
    # Compare against the unchanged first PSD pose. A preexisting source
    # shading patch is not evidence of a NEW side-view cavity.
    original_side_material=lower_fruit_side_gold(first)
    return_side=[]
    for i in range(int(len(order)*.60),int(len(order)*.81)):
        with Image.open(order[i][1]) as frame:
            return_side.append({"frame":i,**inspect(frame),
                                **lower_fruit_side_gold(frame)})
    warm_first_side=[]
    for i in range(int(len(order)*.18),int(len(order)*.42)):
        with Image.open(order[i][1]) as frame:
            warm_first_side.append(lower_fruit_side_gold(frame))
    first_limit=max(.012,baseline["lowerFruitGoldToRedFraction"]*1.25)
    return_limit=max(.025,baseline["lowerFruitGoldToRedFraction"]*2.2)
    first_side_spikes=[m["frame"] for m in first_side
                       if m["lowerFruitGoldPixels"]>=16 and
                          m["lowerFruitGoldToRedFraction"]>first_limit]
    return_side_spikes=[m["frame"] for m in return_side if
        (m["lowerFruitGoldPixels"]>=50 and
         m["lowerFruitGoldToRedFraction"]>return_limit) or
        (m["lowerFruitGoldPixels"]>=100 and
         m["lowerFruitGoldFraction"]>=.035)]
    sustained_bright_seam=any(b==a+1 for a,b in zip(return_side_spikes,return_side_spikes[1:]))
    warm_limit=max(.048,max(m["lowerFruitWarmFraction"] for m in warm_first_side)*2.1)
    warm_side_spikes=[m["frame"] for m in return_side
        if m["lowerFruitWarmPixels"]>=80
        and m["lowerFruitRedPixels"]>=1000
        and m["lowerFruitWarmFraction"]>warm_limit]
    sustained_warm_cavity=any(b==a+1
        for a,b in zip(warm_side_spikes,warm_side_spikes[1:]))
    # Genuine licensed 40-frame Cherry run 42958069343/E11E still has a
    # near-black triangular void in return frames 26–28 after the golden rim
    # was removed. A red/gold-only detector returned a false PASS.
    dark_side_spikes=[m["frame"] for m in return_side if
        m["lowerFruitDarkPixels"]>=100 and
        m["lowerFruitDarkFraction"]>=.03 and
        m["lowerFruitRedPixels"]>=1500]
    sustained_dark_hole=any(b==a+1 for a,b in zip(dark_side_spikes,dark_side_spikes[1:]))
    dark_bridge_limit=max(.052,baseline["darkBridgeFraction"]*2.2)
    dark_bridge_pixels_min=max(20,int(baseline["darkBridgePixels"]*.50))
    dark_bridge_spikes=[m["frame"] for m in return_side
        if m["lowerRedSupportPixels"]>=max(200,baseline["lowerRedSupportPixels"]*.10)
        and m["darkBridgePixels"]>=dark_bridge_pixels_min
        and m["darkBridgeFraction"]>dark_bridge_limit]
    sustained_dark_bridge=any(b==a+1
        for a,b in zip(dark_bridge_spikes,dark_bridge_spikes[1:]))
    # One flat muddy brown RGB island can contain 50+ repeated pixels in
    # the real PR123 Editor candidate, while the original 0° PSD contains
    # at most a handful. Earlier "dark" guards required R<110 and missed it.
    brown_base=original_side_material["brownFlatModePixels"]
    def flat_brown_frames(arc):
        return [m["frame"] for m in arc if
            m["lowerFruitRedPixels"]>=300
            and m["brownFlatModePixels"]>=max(
                22, int(m["lowerFruitRedPixels"]*.0055)+1, brown_base*3)]
    brown_flat_frames=flat_brown_frames(return_side)
    first_side_brown_frames=flat_brown_frames(first_side)
    sustained_brown_flat=any(b==a+1
        for a,b in zip(brown_flat_frames,brown_flat_frames[1:]))
    sustained_first_side_brown=any(b==a+1
        for a,b in zip(first_side_brown_frames,first_side_brown_frames[1:]))
    # A candidate that smears warm contact texture into repeated saturated
    # red is ALSO not a continuous berry surface, even without gold or
    # low-light cavity pixels. Compare exact-color mode to the untouched
    # Photoshop source and require two consecutive return-side frames.
    hot_base=original_side_material["hotRedFlatModePixels"]
    hot_flat_frames=[m["frame"] for m in return_side if
        m["lowerFruitRedPixels"]>=300 and
        m["hotRedFlatModePixels"]>=max(
            16,int(m["lowerFruitRedPixels"]*.003)+1,hot_base*4)]
    sustained_hot_flat=any(b==a+1 for a,b in zip(hot_flat_frames,hot_flat_frames[1:]))
    # Independent source-relative SIDE-PLATE evidence. An R=145 clipping
    # floor dominated 46%/32% of genuine Editor frames 15/16 and 23%/27% of
    # frames 24/25 while the untouched source mode occupied only 7.3%.
    # Exact RGB-mode detectors miss this when the other channels fluctuate.
    # A single side glint cannot trip the gate; two consecutive frames must.
    red_mode_base=original_side_material["redChannelModeFraction"]
    red_mode_limit=max(.21,red_mode_base*3)
    def clipped_red_frames(arc):
        return [m["frame"] for m in arc
                if m["redChannelSupportPixels"]>=300
                and m["redChannelModePixels"]>=100
                and m["redChannelModeFraction"]>red_mode_limit]
    first_side_flat_channel=clipped_red_frames(first_side)
    return_side_flat_channel=clipped_red_frames(return_side)
    def consecutive(frames):
        return any(b==a+1 for a,b in zip(frames,frames[1:]))
    sustained_flat_red_channel=(consecutive(first_side_flat_channel)
                               or consecutive(return_side_flat_channel))
    dark_cavity_frames=sorted(set(dark_side_spikes+dark_bridge_spikes))
    status=("REJECTED_BLOCKY_REAR_MATERIAL" if failures else
            "REJECTED_OVEREXPOSED_REAR_MATERIAL" if overexposed else
            "REJECTED_LOW_REAR_SURFACE_DETAIL" if sustained_low_detail else
            "REJECTED_BRIGHT_RETURN_SIDE_SEAM" if sustained_bright_seam else
            "REJECTED_DARK_RETURN_SIDE_CAVITY" if (sustained_dark_hole or sustained_dark_bridge) else
            "REJECTED_FLAT_BROWN_RETURN_SIDE_CAVITY" if sustained_brown_flat else
            "REJECTED_WARM_RETURN_SIDE_CAVITY" if sustained_warm_cavity else
            "REJECTED_FLAT_BROWN_FIRST_SIDE_CAVITY" if sustained_first_side_brown else
            "REJECTED_FLAT_HOT_RED_RETURN_SIDE_CAVITY" if sustained_hot_flat else
            "REJECTED_FLAT_RED_SIDE_CHANNEL" if sustained_flat_red_channel else
            "PASS_GEOMETRIC_PIXEL_HEURISTIC")
    return {
        "kind":"2spine-native-editor-360-visual-regression",
        "officialEditorFrames":len(order),
        "sourceClosurePixelExact":True,
        "fruitBounds":[x0,y0,x1,y1],
        "baseline":baseline,
        "rearArc":backs,
        "severeRectangleFrames":[m["frame"] for m in failures],
        "overexposedRearFrames":[m["frame"] for m in overexposed],
        "rearClippingLimit":clipping_limit,
        "rearDetailLimit":detail_limit,
        "lowDetailRearFrames":[m["frame"] for m in low_detail],
        "sustainedLowRearDetail":sustained_low_detail,
        "goldFirstSideWarningFrames":first_side_spikes,
        "goldReturnSideSeamFrames":return_side_spikes,
        "returnSideGoldMetrics":[{k:m[k] for k in
          ("frame","lowerFruitRedPixels","lowerFruitGoldPixels","lowerFruitGoldFraction",
           "lowerFruitDarkPixels","lowerFruitDarkFraction",
           "lowerFruitWarmPixels","lowerFruitWarmFraction",
           "lowerRedSupportPixels","darkBridgePixels","darkBridgeFraction",
           "brownFlatModePixels","brownFlatModeRGB","brownFlatModeFraction",
           "hotRedFlatModePixels","hotRedFlatModeRGB",
           "redChannelModeValue","redChannelModePixels",
           "redChannelSupportPixels","redChannelModeFraction")}
          for m in return_side],
        "goldReturnSideSeamDetected":sustained_bright_seam,
        "warmReturnSideCavityFrames":warm_side_spikes,
        "warmReturnSideCavityDetected":sustained_warm_cavity,
        "warmReturnSideFractionLimit":round(warm_limit,6),
        "darkReturnSideCavityFrames":dark_cavity_frames,
        "darkReturnSideCavityDetected":sustained_dark_hole or sustained_dark_bridge,
        "darkReturnSideBridgeFrames":dark_bridge_spikes,
        "darkReturnSideBridgeDetected":sustained_dark_bridge,
        "brownFlatReturnSideFrames":brown_flat_frames,
        "brownFlatReturnSideDetected":sustained_brown_flat,
        "brownFlatFirstSideFrames":first_side_brown_frames,
        "brownFlatFirstSideDetected":sustained_first_side_brown,
        "brownFlatSourceModePixels":brown_base,
        "hotRedFlatReturnSideFrames":hot_flat_frames,
        "hotRedFlatReturnSideDetected":sustained_hot_flat,
        "hotRedFlatSourceModePixels":hot_base,
        "flatRedFirstSideFrames":first_side_flat_channel,
        "flatRedReturnSideFrames":return_side_flat_channel,
        "flatRedChannelDetected":sustained_flat_red_channel,
        "sourceRedModeFraction":red_mode_base,
        "flatRedChannelFractionLimit":round(red_mode_limit,6),
        "darkBridgeFractionLimit":round(dark_bridge_limit,6),
        "darkBridgePixelsMin":dark_bridge_pixels_min,
        "goldLowerFruitSourceRatio":baseline["lowerFruitGoldToRedFraction"],
        "goldReturnSideFractionLimit":round(return_limit,6),
        "status":status,
        "editorTechnicalImportApproved":None,
        "artisticQualityApproved":False,
        "rearArtworkArtistApproved":False,
        "publicationReady":False,
        "limitations":"This is a targeted rectangle/overexposure/closure heuristic, NOT art approval. Review every frame, leaf, stem, overlap, material and silhouette."
    }

def run(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--frames-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    paths=sorted(args.frames_dir.rglob("*.png"))
    report=audit(paths)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("OFFICIAL_SPINE_360_VISUAL_GATE",json.dumps({
      "status":report["status"],"severeRectangleFrames":report["severeRectangleFrames"],
      "overexposedRearFrames":report["overexposedRearFrames"],
      "lowDetailRearFrames":report["lowDetailRearFrames"],
      "goldReturnSideSeamFrames":report["goldReturnSideSeamFrames"],
      "darkReturnSideCavityFrames":report["darkReturnSideCavityFrames"],
      "brownFlatReturnSideFrames":report["brownFlatReturnSideFrames"],
      "warmReturnSideCavityFrames":report["warmReturnSideCavityFrames"],
      "brownFlatFirstSideFrames":report["brownFlatFirstSideFrames"],
      "hotRedFlatReturnSideFrames":report["hotRedFlatReturnSideFrames"],
      "flatRedFirstSideFrames":report["flatRedFirstSideFrames"],
      "flatRedReturnSideFrames":report["flatRedReturnSideFrames"],
      "artisticQualityApproved":False
    }))
    if report["severeRectangleFrames"]:
        raise SystemExit("Rejected: reconstructed 360 rear becomes a flat rectangular plate")
    if report["overexposedRearFrames"]:
        raise SystemExit("Rejected: inferred rear material is overexposed and visually flat")
    if report["sustainedLowRearDetail"]:
        raise SystemExit("Rejected: inferred rear fruit lost detailed material texture across 3+ Editor frames")
    if report["goldReturnSideSeamDetected"]:
        raise SystemExit("Rejected: returning 360 side exposes a bright lower-fruit material hole in consecutive Editor frames")
    if report["darkReturnSideCavityDetected"]:
        raise SystemExit("Rejected: returning 360 side retains a dark internal fruit cavity despite recolored contours")
    if report["warmReturnSideCavityDetected"]:
        raise SystemExit("Rejected: returning 360 side exposes a sustained warm orange-brown material hole")
    if report["brownFlatReturnSideDetected"]:
        raise SystemExit("Rejected: returning 360 side retains a flat muddy-brown internal fruit cavity despite plausible RGB values")
    if report["brownFlatFirstSideDetected"]:
        raise SystemExit("Rejected: first 360 side retains a flat burgundy/brown cavity while the return side appears fixed")
    if report["hotRedFlatReturnSideDetected"]:
        raise SystemExit("Rejected: returning 360 side contains a flat hot-red contact-colour island across real Editor frames")
    if report["flatRedChannelDetected"]:
        raise SystemExit("Rejected: inferred Cherry side has a clipped flat red-channel plate across consecutive licensed Editor frames")

if __name__=="__main__":
    run()
