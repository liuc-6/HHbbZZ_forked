#!/usr/bin/env python3
# python3 post_proc.py -i your.root -n 0 --mode 4l2j
import os
import sys
import argparse

from PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor import PostProcessor
from PhysicsTools.NanoAODTools.postprocessing.modules.common.muonScaleResProducer import *
from PhysicsTools.NanoAODTools.postprocessing.modules.jme.jetmetHelperRun2 import createJMECorrector
from PhysicsTools.NanoAODTools.postprocessing.modules.btv.btagSFProducer import btagSFProducer
from PhysicsTools.NanoAODTools.postprocessing.modules.common.puWeightProducer import *

# Corrections configuration
from corrections_config import get_corrections_modules, get_pu_weight_module

# Custom module imports
from H4Lmodule import *
from H4LCppModule import *
from JetSFMaker import *

def parse_arguments():
    """Parse command line arguments."""
    def str2bool(value):
        if isinstance(value, bool):
            return value
        value = value.lower()
        if value in ("true", "1", "yes", "y"):
            return True
        if value in ("false", "0", "no", "n"):
            return False
        raise argparse.ArgumentTypeError("Boolean value expected.")

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputFile", default="", type=str, help="Input file name")
    parser.add_argument("-n", "--entriesToRun", default=100, type=int,help="Set to 0 if need to run over all entries else put number of entries to run")
    parser.add_argument("-d", "--DownloadFileToLocalThenRun", default=True, type=str2bool,help="Download file to local then run")
    parser.add_argument("-o", "--outputDir", default=".", type=str, help="Output directory")
    parser.add_argument("--dataset", default="", help="Full DAS dataset name; required for unambiguous data processing")
    parser.add_argument("--primaryDataset", default="", help="Primary dataset override for local data tests")
    parser.add_argument("--nanoVersion", type=int, choices=[12, 13, 15], help="NanoAOD version override")
    parser.add_argument("--NOsyst", default=False, action="store_true", help="Do not run systematics")
    parser.add_argument("--overwritePt", default=True, type=bool,help="overwrite muon pt from muon scale and res corrections")
    parser.add_argument("--mode", default="4l2j", choices=["4l", "2l2j", "4l1j", "4l2j"],help="Analysis mode: 4l, 2l2j, 4l1j, or 4l2j")
    return parser.parse_args()

def getListFromFile(filename):
    """Read file list from a text file."""
    with open(filename, "r") as file:
        return ["root://cms-xrd-global.cern.ch/" + line.strip() for line in file]


def main():
    args = parse_arguments()

    # Initial setup
    testfilelist = []
    modulesToRun = []
    isMC = True
    isFSR = False
    year = None
    data_tag = ""
    cfgFile = None
    jsonFileName = None
    sfFileName = None
    overwritePt = args.overwritePt
    analysisMode = args.mode
    outputDir = args.outputDir

    entriesToRun = int(args.entriesToRun)
    DownloadFileToLocalThenRun = args.DownloadFileToLocalThenRun

    # Determine list of files to process
    if args.inputFile.endswith(".txt"):
        testfilelist = getListFromFile(args.inputFile)
    elif args.inputFile.endswith(".root"):
        testfilelist.append(args.inputFile)
    else:
        print("INFO: No input file specified. Using default file list.")
        testfilelist = getListFromFile("ExampleInputFileList.txt")

    print(("DEBUG: Input file list: {}".format(testfilelist)))
    if len(testfilelist) == 0:
        print("ERROR: No input files found. Exiting.")
        exit(1)

    # Dataset metadata is authoritative because data LFNs omit campaign and primary dataset.
    first_file = testfilelist[0]
    metadata_source = args.dataset or first_file
    if args.dataset:
        if not args.dataset.startswith("/") or not args.dataset.endswith(("/NANOAOD", "/NANOAODSIM")):
            raise RuntimeError("--dataset must be a full DAS NANOAOD(SIM) dataset name")
        isMC = args.dataset.endswith("/NANOAODSIM")
    else:
        isMC = "/data/" not in metadata_source
    primary_dataset = args.primaryDataset
    if not isMC and args.dataset:
        primary_dataset = args.dataset.split("/")[1]

    print(first_file, "\n isMC = ", isMC, "\n dataset = ", args.dataset or "<inferred>")

    if "Summer22" in metadata_source or "Run2022" in metadata_source:
        year = 2022
        if isMC:
            if "22EE" in metadata_source:
                data_tag = "post_EE"
            else:
                data_tag = "pre_EE"
            
            jsonFileName = None  # Golden JSON is only used for data, not for MC
        else:
            if ("Run2022E" in metadata_source) or ("Run2022F" in metadata_source) or ("Run2022G" in metadata_source):
                data_tag = "post_EE"
            else:
                data_tag = "pre_EE"
                
            jsonFileName = "golden_Json/Cert_Collisions2022_355100_362760_Golden.json"
            
        cfgFile = "Input_2022.yml"
        sfFileName = "DeepCSV_102XSF_V2.csv"  # FIXME: Update for year 2022

    elif "Summer23" in metadata_source or "Run2023" in metadata_source:
        year = 2023
        if isMC:
            if "23BPix" in metadata_source:
                data_tag = "post_BPix"
            else:
                data_tag = "pre_BPix"
                
            jsonFileName = None  # Golden JSON is only used for data, not for MC
        else:
            if "Run2023D" in metadata_source:
                data_tag = "post_BPix"
            else:
                data_tag = "pre_BPix"
                
            jsonFileName = "golden_Json/Cert_Collisions2023_366442_370790_Golden.json"
            
        cfgFile = "Input_2023.yml"
        sfFileName = "DeepCSV_102XSF_V2.csv"  # FIXME: Update for year 2023

    elif "Summer24" in metadata_source or "Run2024" in metadata_source:
        year = 2024
        data_tag = None            
        cfgFile = "Input_2024.yml"
        
        if isMC:
            jsonFileName = None  # Golden JSON is only used for data, not for MC
        else:
            jsonFileName = "golden_Json/Cert_Collisions2024_378981_386951_Golden.json"
            
        sfFileName = "DeepCSV_102XSF_V2.csv"  # FIXME: Update for year 2024

    elif "UL18" in metadata_source or "UL2018" in metadata_source:
        year = 2018
        cfgFile = "Input_2018.yml"
        jsonFileName = "golden_Json/Cert_314472-325175_13TeV_Legacy2018_Collisions18_JSON.txt"
        sfFileName = "DeepCSV_102XSF_V2.csv"

    elif "UL17" in metadata_source or "UL2017" in metadata_source:
        year = 2017
        cfgFile = "Input_2017.yml"
        jsonFileName = "golden_Json/Cert_294927-306462_13TeV_UL2017_Collisions17_GoldenJSON.txt"
        sfFileName = "DeepCSV_102XSF_V2.csv"

    elif "UL16" in metadata_source or "UL2016" in metadata_source:
        year = 2016
        cfgFile = "Input_2016.yml"
        jsonFileName = "golden_Json/Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt"
        sfFileName = "DeepCSV_102XSF_V2.csv"

    else:
        print("ERROR: Could not determine year from input file name.")
        exit(1)

    if args.nanoVersion:
        nanoVersion = args.nanoVersion
    elif "NanoAODv12" in metadata_source or "NANOAODv12" in metadata_source:
        nanoVersion = 12
    elif "NanoAODv13" in metadata_source or "NANOAODv13" in metadata_source:
        nanoVersion = 13
    elif "NanoAODv15" in metadata_source or "NANOv15" in metadata_source:
        nanoVersion = 15
    elif isMC:
        raise RuntimeError("Cannot determine nanoVersion from MC metadata: {}".format(metadata_source))
    else:
        nanoVersion = 12

    if not isMC and not primary_dataset:
        raise RuntimeError("Data processing requires --dataset or --primaryDataset for trigger de-duplication")
    print("Determined nanoVersion: {}".format(nanoVersion))
    print("Primary dataset: {}".format(primary_dataset or "MC"))
    
    modulesToRun.extend(
        get_corrections_modules(year, data_tag, metadata_source, isMC, overwritePt, nanoVersion)
    )
    
    # ---------------------------
    # analysisMode-dependent preselection
    # ---------------------------
    if analysisMode == "2l2j":
        preselection_cut = "Sum$(Muon_pt>20) + Sum$(Electron_pt>25) >= 2"
    else:
        # for 4l, 4l1j and 4l2j
        preselection_cut = "Sum$(Muon_pt>3) + Sum$(Electron_pt>5) >= 4"

    # main analysis module
    modulesToRun.append(HZZAnalysisCppProducer(year, cfgFile, isMC, isFSR, analysisMode, nanoVersion, primary_dataset))

    print(("Input json file: {}".format(jsonFileName)))
    print(("Input cfg file: {}".format(cfgFile)))
    print(("isMC: {}".format(isMC)))
    print(("isFSR: {}".format(isFSR)))
    print(("analysisMode: {}".format(analysisMode)))
    print(("preselection_cut: {}".format(preselection_cut)))

    if isMC:
        if not args.NOsyst:
            # FIXME: JES not used properly
            # jetmetCorrector = createJMECorrector(isMC=isMC, dataYear=year, jesUncert="All", jetType="AK4PFchs")
            # fatJetCorrector = createJMECorrector(isMC=isMC, dataYear=year, jesUncert="All", jetType="AK8PFPuppi")
            # btagSF = lambda: btagSFProducer("UL"+str(year), algo="deepjet", selectedWPs=['L','M','T','shape_corr'], sfFileName=sfFileName)
            # btagSF = lambda: btagSFProducer(era="UL"+str(year), algo="deepcsv")
            puidSF = lambda: JetSFMaker("%s" % year)
            # modulesToRun.extend([jetmetCorrector(), fatJetCorrector()])  # , puidSF()
            # modulesToRun.extend([jetmetCorrector(), fatJetCorrector(), btagSF(), puidSF()])

        # PU reweight
        if year == 2018:
            modulesToRun.extend([puAutoWeight_2018()])
        if year == 2017:
            modulesToRun.extend([puAutoWeight_2017()])
        if year == 2016:
            modulesToRun.extend([puAutoWeight_2016()])

        # PU weight for 2022, 2023 and 2024
        pu_weight_module = get_pu_weight_module(year, data_tag)
        if pu_weight_module is not None:
            modulesToRun.insert(0, pu_weight_module)

        # INFO: Keep the `fwkJobReport=False` to trigger `haddnano.py`
        # otherwise the output file will have larger size than expected.
        p = PostProcessor(
            outputDir,
            testfilelist,
            #cut = "(Sum$(Muon_pt>3) + Sum$(Electron_pt>5) >= 4) && (nJet>=2)",
            cut=preselection_cut,
            branchsel=None,
            modules=modulesToRun,
            provenance=True,
            fwkJobReport=True,
            haddFileName="skimmed_nano.root",
            maxEntries=entriesToRun,
            prefetch=DownloadFileToLocalThenRun,
            outputbranchsel="keep_and_drop.txt"
        )

    else:
        # if (not args.NOsyst):
        #     FIXME: JES not used properly
        #     jetmetCorrector = createJMECorrector(isMC=isMC, dataYear=year, jesUncert="All", jetType="AK4PFchs")
        #     fatJetCorrector = createJMECorrector(isMC=isMC, dataYear=year, jesUncert="All", jetType="AK8PFPuppi")
        #     modulesToRun.extend([jetmetCorrector(), fatJetCorrector()])

        p = PostProcessor(
            outputDir,
            testfilelist,
            # cut = "(Sum$(Muon_pt>3) + Sum$(Electron_pt>5) >= 4) && (Sum$(Jet_pt>20)>=2)",
            cut=preselection_cut,
            branchsel=None,
            modules=modulesToRun,
            provenance=True,
            fwkJobReport=True,
            haddFileName="skimmed_nano.root",
            jsonInput=jsonFileName,
            maxEntries=entriesToRun,
            prefetch=DownloadFileToLocalThenRun,
            outputbranchsel="keep_and_drop_data.txt"
        )

    p.run()


if __name__ == "__main__":
    main()
