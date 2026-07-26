# Example Usage:
#
# python Utils/nanoAOD_condor_resubmit.py --dir condor_logs/Run2017_v7_18Aug2020_Hadd/200817_180337/ -s /eos/uscms/store/user/lnujj/VVjj_aQGC/nanoAOD_skim/Run2017_v7_18Aug2020_Hadd -i submit_condor_jobs_lnujj_Run2017_v7_18Aug2020_Hadd.jdl
#
# Fix hardcoded number 7

import os
from optparse import OptionParser
import ROOT
from ROOT import TFile

DEBUG = False

def files_to_remove(files,dir):
  filelist_to_remove = []
  for file in files:
    try:
      tfile = TFile.Open(file);
    except:
      pass
    if tfile:
      if (tfile.IsZombie()):
        filelist_to_remove.append(file)
    else:
      print('File could not be opened, adding it to missing files')
      filelist_to_remove.append(os.path.basename(file).replace("_SkimHadd","").replace("_Skim",""))

  if DEBUG: print(filelist_to_remove)
  return filelist_to_remove

def list_files(file_name):
  with open(file_name) as f:
    datafile = f.readlines()
    file_list = []
    for line in datafile:
      if "USER_" in line:
        start_pt = line.find("output")
        end_pt = line.find(".root", start_pt + 1)
        res = line[start_pt:end_pt+5]
        if "/" in res :
            res = res[res.find("/")+1:]
        file_list.append(res)
  return file_list

def get_files_from_jdl(path_jdl):
  flist = []
  with open(path_jdl) as myfile:
    for line in myfile:
      if not line.startswith("Arguments = "):
        continue
      fields = line.strip().split()
      if len(fields) < 3:
        continue
      flist.append(fields[2].split('/')[-1])
  return flist

def get_jdl_header(path_jdl):
  header = []
  with open(path_jdl) as myfile:
    for line in myfile:
      if line.startswith("Output = "):
        break
      header.append(line)
  return header

def get_jdl_job_blocks(path_jdl):
  blocks = {}
  current_block = []
  with open(path_jdl) as myfile:
    for line in myfile:
      if line.startswith("Output = "):
        current_block = [line]
        continue
      if not current_block:
        continue
      current_block.append(line)
      if line.startswith("Queue"):
        root_name = ""
        for block_line in current_block:
          if block_line.startswith("Arguments = "):
            fields = block_line.strip().split()
            if len(fields) >= 3:
              root_name = fields[2].split('/')[-1]
            break
        if root_name != "":
          blocks[root_name] = list(current_block)
        current_block = []
  return blocks

def list_root(directory):
  flist = []
  flistWithPath = []
  for root, directories, filenames in os.walk(directory):
    for filename in filenames:
      if filename.endswith(".root"):
        flist.append(filename.replace("_SkimHadd","").replace("_Skim",""))
        fileWithPath = os.path.join(root,filename)  # Get file name with path
        flistWithPath.append(fileWithPath)
  return flist,flistWithPath

def submit_missing(InputJdlFile,resubmit=True):
  bashCommand = "condor_submit %s"%(InputJdlFile)
  if resubmit :
    print('Resubmitting now!')
    os.system(bashCommand)
  else :
    print('Ready to resubmit, please set resubmit to True if you are ready : ')
    print(bashCommand)

def prepare_runJobs_missing(FailedJobRootFile,InputJdlFile,CondorLogDir,EOSDir,Resubmit_no):
  if DEBUG: print("FailedJobRootFile: ",FailedJobRootFile)
  if DEBUG: print("InputJdlFile: ",InputJdlFile)
  if DEBUG: print("CondorLogDir: ",CondorLogDir)
  if DEBUG: print("EOSDir: ",EOSDir)

  bashCommand = "cp %s  original_%s"%(InputJdlFile,InputJdlFile)
  os.system(bashCommand)

  outjdl_fileName = InputJdlFile.replace(".jdl","")+'_resubmit_'+Resubmit_no+".jdl"

  outjdl_file = open(outjdl_fileName,"w")

  head = get_jdl_header(InputJdlFile)
  jdl_blocks = get_jdl_job_blocks(InputJdlFile)

  for lines in head:
    outjdl_file.write(lines)

  for RootFiles in FailedJobRootFile:
    if DEBUG: print(RootFiles)
    grep_condor_jdl_part = ''.join(jdl_blocks.get(RootFiles, []))
    if DEBUG: print("=="*51)
    if DEBUG: print(grep_condor_jdl_part)
    updateString = grep_condor_jdl_part.replace('$(Process)','resubmit_'+Resubmit_no+'_$(Process)')
    if DEBUG: print("=="*51)
    if DEBUG: print(updateString)
    if DEBUG: print("=="*51)
    outjdl_file.write(updateString)
  outjdl_file.close()
  return outjdl_fileName


def main():
  parser = OptionParser()
  parser.add_option("-d", "--dir", dest="dir",default="task_config.json",help="directory")
  parser.add_option("-s", "--stage-dest", dest="stage_dest",help="directory output files were staged to")
  parser.add_option("-i", "--input", dest="input",default="all_root.jdl",help="input jdl file with all root files present")
  parser.add_option("-r", "--resubmit", action="store_false",  dest="resubmit",default=True,help="resubmit")
  parser.add_option("-n", "--resubmit_no", dest="resubmit_no",default=1,help="resubmit counter")

  (options, args) = parser.parse_args()

  if options.stage_dest is not None:
    stageDir = os.path.abspath(options.stage_dest)
  else:
    stageDir = options.dir

  full_output =  get_files_from_jdl(options.input)
  # print full_output
  present_output, present_output_WithPath =  list_root(stageDir)
  # print present_output
  print("length(jdl file): ",len(full_output))
  print("Length(output root file): ",len(present_output))
  not_finished = list(set(full_output) - set(present_output))
  print(not_finished)
  corrupted_files = files_to_remove(present_output_WithPath,stageDir)
  not_finished += corrupted_files
  print(not_finished)
  print('Number of missing files : ',len(not_finished))
  print('Missing the following files : ',not_finished)
  jdlfile = prepare_runJobs_missing(not_finished,options.input,options.dir,stageDir,str(options.resubmit_no))
  print(jdlfile)
  print('Submitting missing jobs : ')
  submit_missing(jdlfile,options.resubmit)



if __name__ == "__main__":
    main()
