"""Run-3 CMS HZZ-specific electron identification scale factors.

Maps and special-region logic ported from:
https://github.com/CJLST/ZZAnalysis/blob/Run3/AnalysisStep/src/LeptonSFHelper.cc

Only the electron ID/selection SF is returned. Electron reconstruction SF must be applied separately.
These files are only available for electrons with pt > 7GeV !!!

"""

import math
import os
import ROOT


class HZZElectronIDSF:
    def __init__(self, year, data_tag, base_dir=None):
        self.year = int(year)
        self.data_tag = data_tag
        
        self.base_dir = os.path.expandvars(
            base_dir or os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))
                ),
                "data",
                "Run3_LepSF",
                "Electron_HZZID"
            )
        )

        if self.year == 2022:
            if data_tag == "pre_EE":
                default_name = "SF2022eleID_preEE.root"
            elif data_tag == "post_EE":
                default_name = "SF2022eleID_postEE.root"
            else:
                raise ValueError("2022 requires pre_EE or post_EE, got %r" % data_tag)
            gap_name = None
            hole_name = None
        elif self.year == 2023:
            if data_tag == "pre_BPix":
                default_name = "SF2023eleID_preBPix.root"
                hole_name = None
            elif data_tag == "post_BPix":
                default_name = "SF2023eleID_postBPix.root"
                hole_name = "SF2023eleID_postBPix_Hole.root"
            else:
                raise ValueError("2023 requires pre_BPix or post_BPix, got %r" % data_tag)
            gap_name = "SF2023eleID_Gap_preBPix.root"
        elif self.year == 2024:
            default_name = "SF2024eleID.root"
            gap_name = "SF2024eleID_Gap.root"
            hole_name = None
        else:
            raise ValueError("HZZ Electron ID SF supported only for 2022, 2023, 2024")

        self.default = self._load(default_name)
        self.gap = self._load(gap_name) if gap_name else None
        self.hole = self._load(hole_name) if hole_name else None

    def _load(self, filename):
        full_path = os.path.join(self.base_dir, filename)
        if not os.path.isfile(full_path):
            raise FileNotFoundError("Missing HZZ SF ROOT file: " + full_path)
        f = ROOT.TFile.Open(full_path, "READ")
        if not f or f.IsZombie():
            raise OSError("Cannot open HZZ SF ROOT file: " + full_path)
        source = f.Get("EGamma_SF2D")
        if not source or not source.InheritsFrom("TH2"):
            f.Close()
            raise KeyError("Missing TH2 'EGamma_SF2D' in: " + full_path)
        hist = source.Clone("hzz_ele_sf_" + filename.replace(".", "_"))

        hist.SetDirectory(0)
        f.Close()
        return hist

    def evaluate(self, pt, eta, delta_eta_sc, phi):
        """Return (nominal SF, SF+absolute bin error, SF-absolute bin error).

        Inputs: corrected, *undressed* Electron_pt, Electron_eta,
        Electron_deltaEtaSC, Electron_phi; use the ORIGINAL collection indices.
        """
        pt = float(pt)
        sceta = float(eta) + float(delta_eta_sc)
        phi = float(phi)
        if not all(math.isfinite(x) for x in (pt, sceta, phi)):
            raise ValueError("Non-finite electron input for HZZ SF")

        is_gap = 1.444 < abs(sceta) < 1.556
        use_gap = (self.year in (2023, 2024) and pt < 20.0 and is_gap)
        is_hole = (-1.5 < sceta < 0.0) and (-1.2 < phi < -0.8)

        if use_gap:
            h = self.gap
        elif self.year == 2023 and self.data_tag == "post_BPix" and is_hole:
            h = self.hole
        else:
            h = self.default

        # Follow the HZZ helper's upper-pt treatment, but never silently use
        # underflow or overflow bins for inputs outside the map acceptance.
        ypt = min(pt, 499.0)
        xax, yax = h.GetXaxis(), h.GetYaxis()
        bx, by = xax.FindFixBin(sceta), yax.FindFixBin(ypt)
        if not (1 <= bx <= h.GetNbinsX() and 1 <= by <= h.GetNbinsY()):
            raise ValueError(
                "HZZ electron ID SF outside map: year=%s tag=%s "
                "pt=%g SCeta=%g file=%s xRange=(%g,%g) yRange=(%g,%g)" % (
                    self.year, self.data_tag, pt, sceta,
                    "gap" if use_gap else "hole" if h is self.hole else "default",
                    xax.GetXmin(), xax.GetXmax(), yax.GetXmin(), yax.GetXmax())
            )
        nominal = float(h.GetBinContent(bx, by))
        absolute_error = float(h.GetBinError(bx, by))
        if not (math.isfinite(nominal) and math.isfinite(absolute_error)
                and nominal > 0 and absolute_error >= 0):
            raise ValueError("Invalid HZZ electron SF bin: SF=%g error=%g" % (nominal, absolute_error))

        # HZZ helper: for 2023 postBPix low-pt ECAL gap, double uncertainty.
        if use_gap and self.year == 2023 and self.data_tag == "post_BPix":
            absolute_error *= 2.0

        return (nominal, nominal + absolute_error,
                max(0.0, nominal - absolute_error))
