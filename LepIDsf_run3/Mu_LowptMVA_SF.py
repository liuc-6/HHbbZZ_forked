"""Run-3 HZZ Low-pT-MVA muon selection scale factors (2022--2024).

Reference: CJLST/ZZAnalysis, Run3, AnalysisStep/src/LeptonSFHelper.cc.
Maps: AnalysisStep/data/LeptonEffScaleFactors/Muon_LowPtMVA/*.root

FINAL: TH2 nominal SF (x=Muon_eta, y=Muon_pt)
ERROR: TH2 absolute uncertainty, taken from GetBinContent (NOT bin error)

These files are only available for muons with pt > 5GeV !!!
"""
import math
import os
import ROOT


class HZZMuonLowPtMVASF:
    FILES = {
        (2022, 'pre_EE'): 'final_HZZ_SF_Run3_2022_mupogsysts_newLoose_abseta3_fix_BCD_RMS.root',
        (2022, 'post_EE'): 'final_HZZ_SF_Run3_2022_mupogsysts_newLoose_abseta3_fix_EFG_RMS.root',
        (2023, 'pre_BPix'): 'final_HZZ_SF_2023C_RMS_mupogsysts.root',
        (2023, 'post_BPix'): 'final_HZZ_SF_2023D_RMS_mupogsysts.root',
        (2024, None): 'HZZ_HZZ_SF_2024_RMS_mupogsystsC.root',
    }

    def __init__(self, year, data_tag=None, base_dir=None):
        self.year = int(year)
        self.data_tag = data_tag
        key = (self.year, None if self.year == 2024 else self.data_tag)
        if key not in self.FILES:
            raise ValueError('Unsupported HZZ muon SF era: %r (expected %s)' %
                             (key, list(self.FILES)))
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    'data', 'Run3_LepSF', 'Muon_LowPtMVA')
        self.base_dir = os.path.expandvars(os.path.expanduser(base_dir))
        self.path = os.path.join(self.base_dir, self.FILES[key])
        if not os.path.isfile(self.path):
            raise FileNotFoundError('Missing HZZ LowPtMVA muon ROOT file: ' + self.path)

        f = ROOT.TFile.Open(self.path, 'READ')
        if not f or f.IsZombie():
            raise OSError('Failed to open ROOT file: ' + self.path)
        try:
            self.sf = self._clone(f, 'FINAL', 'mu_hzz_lowptmva_sf')
            self.error = self._clone(f, 'ERROR', 'mu_hzz_lowptmva_unc')
        finally:
            f.Close()

        for axisname in ('GetXaxis', 'GetYaxis'):
            a = getattr(self.sf, axisname)()
            b = getattr(self.error, axisname)()
            if (a.GetNbins() != b.GetNbins() or
                    a.GetXmin() != b.GetXmin() or a.GetXmax() != b.GetXmax()):
                raise ValueError('FINAL and ERROR map binning mismatch in ' + self.path)
            

    @staticmethod
    def _clone(file, name, prefix):
        src = file.Get(name)
        if not src or not src.InheritsFrom('TH2'):
            raise KeyError('Missing ROOT TH2 histogram %s' % name)
        h = src.Clone('%s_%d' % (prefix, id(src)))
        h.SetDirectory(0)
        return h

    def evaluate(self, pt, eta):
        """Return (nominal, nominal+absolute_error, nominal-absolute_error).

        The caller should skip selected muons with pt < 5 GeV and mark the
        event SF as partially outside the HZZ measured acceptance.
        """
        pt, eta = float(pt), float(eta)
        if not (math.isfinite(pt) and math.isfinite(eta)):
            raise ValueError('Nonfinite muon pt or eta')
        if pt < 5.0:
            raise ValueError('Muon pT below 5 GeV HZZ SF acceptance: %g' % pt)
        # Follow official LeptonSFHelper.cc overflow protection.
        map_pt = min(pt, 199.0)
        xaxis, yaxis = self.sf.GetXaxis(), self.sf.GetYaxis()
        bx = xaxis.FindFixBin(eta)
        by = yaxis.FindFixBin(map_pt)
        if not (1 <= bx <= self.sf.GetNbinsX() and
                1 <= by <= self.sf.GetNbinsY()):
            raise ValueError(
                'HZZ LowPtMVA muon outside SF map: pt=%g eta=%g ' 
                'xRange=(%g,%g) yRange=(%g,%g) file=%s' %
                (pt, eta, xaxis.GetXmin(), xaxis.GetXmax(),
                 yaxis.GetXmin(), yaxis.GetXmax(), self.path))
        sf = float(self.sf.GetBinContent(bx, by))
        absolute_error = float(self.error.GetBinContent(bx, by))
        if not (math.isfinite(sf) and sf > 0 and
                math.isfinite(absolute_error) and absolute_error >= 0):
            raise ValueError('Invalid muon SF=%r error=%r in %s' %
                             (sf, absolute_error, self.path))
        return sf, sf + absolute_error, max(0.0, sf - absolute_error)
