"""
# How to run:
python3 condor_setup_lxplus.py
"""
import argparse
import os
import shutil
import sys

sys.path.append("Utils/.")

from color_style import style

CANONICAL_TARBALL = (
    "/eos/user/l/lyifan/nanoAOD_ntuples5320/canonical/"
    "CMSSW_15_1_1_20260725_v4.tgz"
)

def main(args):

    # Variables from argparse
    submission_name = args.submission_name
    use_custom_eos = args.use_custom_eos
    use_custom_eos_cmd = args.use_custom_eos_cmd
    InputFileFromWhereReadDASNames = args.input_file
    analysisMode = args.mode
    EOS_Output_path = args.eos_output_path
    if EOS_Output_path == "":
        # Keep all skim productions under one EOS root; submission_name is appended below.
        username = os.environ['USER']
        user_initials = username[0:1]
        EOS_Output_path = '/eos/user/'+user_initials+'/'+username+'/nanoAOD_ntuples5320'
    if submission_name != "":
        EOS_Output_path = EOS_Output_path + '/' + submission_name
    condor_log_path = args.condor_log_path

    # Get top-level directory name from PWD
    TOP_LEVEL_DIR_NAME = os.path.basename(os.getcwd())
    condor_file_name = args.condor_file_name
    condor_queue = args.condor_queue
    condor_file_name = 'submit_condor_jobs_lnujj_'+submission_name
    username = os.environ.get('USER', '')
    user_initials = username[0:1]
    condor_job_area = args.condor_job_area
    if condor_job_area == "":
        condor_job_area = '/eos/user/'+user_initials+'/'+username+'/For_HHbb4l_condor'
    condor_submit_dir = os.path.join(condor_job_area, submission_name)
    os.makedirs(condor_submit_dir, exist_ok=True)

    # Create log files
    import infoCreaterGit
    if args.summary != "":
        SummaryOfCurrentSubmission = args.summary
    else:
        SummaryOfCurrentSubmission = input("\n\nWrite summary for current job submission: ")
    infoLogFiles = infoCreaterGit.BasicInfoCreater('summary.dat',SummaryOfCurrentSubmission)
    infoLogFiles.generate_git_patch_and_log()
    shutil.copy2('summary.dat', os.path.join(condor_submit_dir, 'summary.dat'))
    shutil.copy2(infoLogFiles.GITPATCH, os.path.join(condor_submit_dir, infoLogFiles.GITPATCH))

    # Get CMSSW directory path and name
    cmsswDirPath = os.environ['CMSSW_BASE']
    CMSSWRel = cmsswDirPath.split("/")[-1]

    # Create directories for storing log files and output files at EOS.
    import fileshelper
    if condor_log_path == './':
        condor_log_path = condor_submit_dir
    dirsToCreate = fileshelper.FileHelper( (condor_log_path + '/condor_logs/'+submission_name).replace("//","/"), EOS_Output_path)
    output_log_path = dirsToCreate.create_log_dir_with_date()
    storeDir = dirsToCreate.create_store_area(EOS_Output_path)
    dirName = dirsToCreate.dir_name

    # Worker payloads are intentionally pinned to this tested canonical tarball.
    # Repository edits are not packaged automatically. If the repository must be
    # changed, rebuild and replace CANONICAL_TARBALL directly before submitting.
    tarball_path = CANONICAL_TARBALL
    if not os.path.isfile(tarball_path):
        raise RuntimeError("Canonical tarball does not exist: "+tarball_path)
    print(("Using pinned canonical tarball: "+tarball_path))

    post_proc_to_run = "post_proc.py"
    command = "python3 "+post_proc_to_run

    proxy_path = os.environ.get("X509_USER_PROXY", "")
    proxy_for_condor = "$ENV(X509_USER_PROXY)"
    if proxy_path != "" and os.path.exists(proxy_path):
        proxy_for_condor = os.path.join(condor_submit_dir, os.path.basename(proxy_path))
        shutil.copy2(proxy_path, proxy_for_condor)
        os.chmod(proxy_for_condor, 0o600)

    jdl_path = os.path.join(condor_submit_dir, condor_file_name+".jdl")
    script_path = os.path.join(condor_submit_dir, condor_file_name+".sh")

    Transfer_Input_Files = ("keep_and_drop.txt")     # FIXME: Generalise this.
    # Transfer_Input_Files = ("Cert_271036-284044_13TeV_PromptReco_Collisions16_JSON.txt, " +
    #                         "Cert_294927-306462_13TeV_PromptReco_Collisions17_JSON.txt, " +
    #                         "Cert_314472-325175_13TeV_PromptReco_Collisions18_JSON.txt, " +
    #                         "keep_and_drop_data.txt")

    #with open('input_data_Files/sample_list_v6_2017_campaign.dat') as in_file:
    with open('input_data_Files/'+InputFileFromWhereReadDASNames) as in_file:
        outjdl_file = open(jdl_path,"w")
        outjdl_file.write("+JobFlavour   = \""+condor_queue+"\"\n")
        outjdl_file.write("Initialdir = "+condor_submit_dir+"\n")
        outjdl_file.write("Executable = "+script_path+"\n")
        outjdl_file.write("Universe = vanilla\n")
        outjdl_file.write("Notification = Never\n")
        outjdl_file.write("Should_Transfer_Files = YES\n")
        outjdl_file.write("WhenToTransferOutput = ON_EXIT\n")
        outjdl_file.write('transfer_output_files = ""\n')
        # Transfer plugins run before the wrapper. Keep their HOME off AFS.
        outjdl_file.write('environment = "HOME=/tmp;XDG_CACHE_HOME=/tmp;PYTHONNOUSERSITE=1"\n')
        outjdl_file.write("x509userproxy = "+proxy_for_condor+"\n")
        outjdl_file.write("requirements = TARGET.OpSysAndVer =?= \"AlmaLinux9\"\n")
        outjdl_file.write("MY.WantOS = \"el9\"\n")
        outjdl_file.write("request_memory = "+str(args.request_memory)+"\n")
        outjdl_file.write("request_disk = "+str(args.request_disk)+"\n")
        outjdl_file.write("Log = "+output_log_path+"/"+submission_name+"_$(ClusterId).log\n")
        count = 0
        count_jobs = 0
        for SampleDASName in in_file:
            if SampleDASName[0] == "#": continue
            count = count +1
            #if count > 1: break
            print((style.RED +"="*51+style.RESET+"\n"))
            print(("==> Sample : ",count))
            sample_name = SampleDASName.split('/')[1]
            print(("==> sample_name = ",sample_name))
            campaign = SampleDASName.split('/')[2].split('-')[0]
            print(("==> campaign = ",campaign))
            ########################################
            #
            #      Create output directory
            #
            ########################################
            if (SampleDASName.strip()).endswith("/NANOAOD"): # if the sample name ends with /NANOAOD, then it is a data if it ends with /NANOAODSIM then it is a MC. As the line contain the "\n" at the end, so we need to use the strip() function.
                output_string = sample_name + os.sep + campaign + os.sep + dirName
                output_path = EOS_Output_path + os.sep + output_string
                print(("==> output_path = ",output_path))
                os.system("mkdir -p "+ output_path)
                infoLogFiles.send_git_log_and_patch_to_eos(output_path)
            else:
                output_string = campaign + os.sep + sample_name + os.sep + dirName
                output_path = EOS_Output_path+ os.sep + output_string
                print(("==> output_path = ",output_path))
                os.system("mkdir -p "+output_path)
                infoLogFiles.send_git_log_and_patch_to_eos(output_path)
            #  print "==> output_path = ",output_path

            ########################################
            #print 'dasgoclient --query="file dataset='+SampleDASName.strip()+'"'
            #print "..."
            if use_custom_eos:
                xrd_redirector = 'root://cms-xrd-global.cern.ch/'
                output = os.popen(use_custom_eos_cmd + SampleDASName.strip()).read()
            else:
                xrd_redirector = 'root://cms-xrd-global.cern.ch/'
                output = os.popen('dasgoclient --query="file dataset='+SampleDASName.strip()+'"').read()

            count_root_files = 0
            for root_file in output.split():
                #print "=> ",root_file
                count_root_files+=1
                count_jobs += 1
                outjdl_file.write("Output = "+output_log_path+"/"+sample_name+"_$(Process).stdout\n")
                outjdl_file.write("Error  = "+output_log_path+"/"+sample_name+"_$(Process).err\n")
                outjdl_file.write("Arguments = "+(xrd_redirector+root_file)+" "+output_path+"  "+EOS_Output_path+ " " + (root_file.split('/')[-1]).split('.')[0] + " " + SampleDASName.strip() + "\n")
                outjdl_file.write("Queue \n")
            print(("Number of files: ",count_root_files))
            print(("Number of jobs (till now): ",count_jobs))
        outjdl_file.close();


    outScript = open(script_path,"w");
    outScript.write('#!/bin/bash');
    outScript.write("\n"+'set -euo pipefail');
    outScript.write("\n"+'export HOME="${_CONDOR_SCRATCH_DIR}"');
    outScript.write("\n"+'export XDG_CACHE_HOME="${_CONDOR_SCRATCH_DIR}/.cache"');
    outScript.write("\n"+'export TMPDIR="${_CONDOR_SCRATCH_DIR}/tmp"');
    outScript.write("\n"+'export PYTHONNOUSERSITE=1');
    outScript.write("\n"+'mkdir -p "${XDG_CACHE_HOME}" "${TMPDIR}"');
    outScript.write("\n"+'cleanup() {');
    outScript.write("\n"+'    cd "${_CONDOR_SCRATCH_DIR}" 2>/dev/null || true');
    outScript.write("\n"+'    rm -rf "'+CMSSWRel+'" "'+CMSSWRel+'.tgz" core core.*');
    outScript.write("\n"+'}');
    outScript.write("\n"+'trap cleanup EXIT');
    outScript.write("\n"+'echo "Starting job on " `date`');
    outScript.write("\n"+'echo "Running on: `uname -a`"');
    outScript.write("\n"+'echo "System software: `cat /etc/redhat-release`"');
    outScript.write("\n"+'source /cvmfs/cms.cern.ch/cmsset_default.sh');
    outScript.write("\n"+'echo "copy cmssw tar file from store area"');
    outScript.write("\n"+'xrdcp -f root://eosuser.cern.ch/'+tarball_path+' '+CMSSWRel+'.tgz');
    outScript.write("\n"+'tar -xf '+ CMSSWRel +'.tgz' );
    outScript.write("\n"+'rm -f '+ CMSSWRel +'.tgz' );
    outScript.write("\n"+'cd ' + CMSSWRel + '/src/PhysicsTools/NanoAODTools/python/postprocessing/analysis/'+TOP_LEVEL_DIR_NAME+'/' );
    #outScript.write("\n"+'echo "====> List files : " ');
    #outScript.write("\n"+'ls -alh');
    outScript.write("\n"+'rm -f ./*.root');
    outScript.write("\n"+'scramv1 b ProjectRename');
    outScript.write("\n"+'eval `scram runtime -sh`');
    outScript.write("\n"+'eval `JHUGenMELA/MELA/setup.sh env`');
    # outScript.write("\n"+'sed -i "s/ifRunningOnCondor = .*/ifRunningOnCondor = True/g" '+post_proc_to_run);
    # outScript.write("\n"+'sed -i "s/testfile = .*/testfile = \\"${1}\\"/g" '+post_proc_to_run);
    outScript.write("\n"+'echo "========================================="');
    outScript.write("\n"+'echo "cat post_proc.py"');
    outScript.write("\n"+'echo "..."');
    outScript.write("\n"+'cat post_proc.py');
    outScript.write("\n"+'echo "..."');
    outScript.write("\n"+'echo "========================================="');
    outScript.write("\n"+command + " --entriesToRun 0 --inputFile \"${1}\" --mode " + analysisMode + " --dataset \"${5}\"");
    outScript.write("\n"+'echo "====> List root files : " ');
    outScript.write("\n"+'ls *.root');
    outScript.write("\n"+'echo "====> copying *.root file to stores area..." ');
    outScript.write("\n"+'if ls skimmed_nano.root 1> /dev/null 2>&1; then');
    outScript.write("\n"+'    echo "File skimmed_nano.root exists. Copy this."');
    outScript.write("\n"+'    echo "cp skimmed_nano.root ${2}/${4}_Skim.root"');
    outScript.write("\n"+'    cp  skimmed_nano.root ${2}/${4}_Skim.root');
    outScript.write("\n"+'else');
    outScript.write("\n"+'    echo "file skimmed_nano.root does not exists, so copy *.root file."');
    outScript.write("\n"+'    echo "cp *.root ${2}/${4}_Skim.root"');
    outScript.write("\n"+'    cp  *.root ${2}/${4}_Skim.root');
    outScript.write("\n"+'fi');
    outScript.write("\n"+'rm -f ./*.root');
    outScript.write("\n");
    outScript.close();
    os.system("chmod 777 "+script_path);

    submit_helper_path = os.path.join(condor_submit_dir, "submit_from_eos.sh")
    submitHelper = open(submit_helper_path, "w")
    submitHelper.write('#!/bin/bash\n')
    submitHelper.write('set -e\n')
    submitHelper.write('cd "$(dirname "$0")"\n')
    submitHelper.write('module load lxbatch/eossubmit\n')
    submitHelper.write('condor_submit '+os.path.basename(jdl_path)+'\n')
    submitHelper.close()
    os.system("chmod 777 "+submit_helper_path)


    print("\n#===> Set Proxy Using:")
    print("voms-proxy-init --voms cms --valid 168:00")
    print("\n# It is assumed that the proxy is created in file: /tmp/x509up_u177472. Update this in below two lines:")
    print("cp /tmp/x509up_u177472 ~/")
    print("export X509_USER_PROXY=~/x509up_u177472")
    print("\n#Submit jobs from the EOS submit directory:")
    print(("cd "+condor_submit_dir))
    print("module load lxbatch/eossubmit")
    print(("condor_submit "+os.path.basename(jdl_path)))
    print("\n# Or, from anywhere, run the EOS-local helper:")
    print(submit_helper_path)
    #os.system("condor_submit "+condor_file_name+".jdl")

# Below patch is to format the help command as it is
class PreserveWhitespaceFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Condor Job Submission", formatter_class=PreserveWhitespaceFormatter)
    parser.add_argument("--submission_name", default="SkimNanoAOD", help="String to be changed by user.")
    parser.add_argument("--use_custom_eos", default=False, action='store_true', help="Use custom EOS.")
    parser.add_argument("--use_custom_eos_cmd", default='eos root://cmseos.fnal.gov find -name "*.root" /store/group/lnujj/VVjj_aQGC/custom_nanoAOD', help="Custom EOS command.")
    # input_file mandatory
    parser.add_argument("--input_file", default='', required=True,  help="Input file from where to read DAS names.")
    parser.add_argument("--eos_output_path", default='', help="EOS root for output files. By default it is `/eos/user/<initial>/<username>/nanoAOD_ntuples5320`; submission_name is appended automatically.")
    parser.add_argument("--condor_log_path", default='./', help="Path where condor log should be saved. By default is the current working directory")
    parser.add_argument("--condor_job_area", default='', help="EOS area where the condor JDL, executable, proxy and logs are stored. Default is /eos/user/<initial>/<user>/For_HHbb4l_condor")
    parser.add_argument("--request_memory", default=8000, type=int, help="Condor request_memory in MB.")
    parser.add_argument("--request_disk", default="8000M", help="Condor request_disk value.")
    parser.add_argument("--summary", default="", help="Submission summary. If empty, prompt interactively.")
    parser.add_argument("--condor_file_name", default='submit_condor_jobs_lnujj_', help="Name for the condor file.")
    parser.add_argument("--condor_queue", default="testmatch", help="""
                        Condor queue options: (Reference: https://twiki.cern.ch/twiki/bin/view/ABPComputing/LxbatchHTCondor#Queue_Flavours)

                        name            Duration
                        ------------------------
                        espresso            20min
                        microcentury     1h
                        longlunch           2h
                        workday 8h        1nd
                        tomorrow           1d
                        testmatch          3d
                        nextweek           1w
                        """)

    parser.add_argument("--post_proc", default="post_proc.py", help="Post process script to run.")
    parser.add_argument("--transfer_input_files", default="keep_and_drop.txt", help="Files to be transferred as input.")
    parser.add_argument("--mode", default="4l2j", choices=["4l", "2l2j", "4l1j", "4l2j"],
                        help="Analysis mode passed to post_proc.py")
    args = parser.parse_args()
    main(args)
#condor_setup_lxplus.py
