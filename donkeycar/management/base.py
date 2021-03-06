
import sys
import os
import socket
import shutil
import argparse
import json
import time

import donkeycar as dk
from donkeycar.parts.datastore import Tub, TubHandler # rbx TubHandler added
from donkeycar.utils import *
from donkeycar.management.tub import TubManager
from donkeycar.management.joystick_creator import CreateJoystick
import numpy as np

from donkeycar.utils import img_to_binary, binary_to_img, arr_to_img, img_to_arr
import cv2

PACKAGE_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
TEMPLATES_PATH = os.path.join(PACKAGE_PATH, 'templates')

def make_dir(path):
    real_path = os.path.expanduser(path)
    print('making dir ', real_path)
    if not os.path.exists(real_path):
        os.makedirs(real_path)
    return real_path


def load_config(config_path):

    '''
    load a config from the given path
    '''
    conf = os.path.expanduser(config_path)

    if not os.path.exists(conf):
        print("No config file at location: %s. Add --config to specify\
                location or run from dir containing config.py." % conf)
        return None

    try:
        cfg = dk.load_config(conf)
    except:
        print("Exception while loading config from", conf)
        return None

    return cfg


class BaseCommand(object):
    pass


class CreateCar(BaseCommand):
    
    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='createcar', usage='%(prog)s [options]')
        parser.add_argument('--path', default=None, help='path where to create car folder')
        parser.add_argument('--template', default=None, help='name of car template to use')
        parser.add_argument('--overwrite', action='store_true', help='should replace existing files')
        
        parsed_args = parser.parse_args(args)
        return parsed_args
        
    def run(self, args):
        args = self.parse_args(args)
        self.create_car(path=args.path, template=args.template, overwrite=args.overwrite)
    
    def create_car(self, path, template='complete', overwrite=False):
        """
        This script sets up the folder structure for donkey to work.
        It must run without donkey installed so that people installing with
        docker can build the folder structure for docker to mount to.
        """

        #these are neeeded incase None is passed as path
        path = path or '~/mycar'
        template = template or 'complete'


        print("Creating car folder: {}".format(path))
        path = make_dir(path)
        
        print("Creating data & model folders.")
        folders = ['models', 'data', 'logs']
        folder_paths = [os.path.join(path, f) for f in folders]   
        for fp in folder_paths:
            make_dir(fp)
            
        #add car application and config files if they don't exist
        app_template_path = os.path.join(TEMPLATES_PATH, template+'.py')
        config_template_path = os.path.join(TEMPLATES_PATH, 'cfg_' + template + '.py')
        myconfig_template_path = os.path.join(TEMPLATES_PATH, 'myconfig.py')
        train_template_path = os.path.join(TEMPLATES_PATH, 'train.py')
        car_app_path = os.path.join(path, 'manage.py')
        car_config_path = os.path.join(path, 'config.py')
        mycar_config_path = os.path.join(path, 'myconfig.py')
        train_app_path = os.path.join(path, 'train.py')
        
        if os.path.exists(car_app_path) and not overwrite:
            print('Car app already exists. Delete it and rerun createcar to replace.')
        else:
            print("Copying car application template: {}".format(template))
            shutil.copyfile(app_template_path, car_app_path)
            
        if os.path.exists(car_config_path) and not overwrite:
            print('Car config already exists. Delete it and rerun createcar to replace.')
        else:
            print("Copying car config defaults. Adjust these before starting your car.")
            shutil.copyfile(config_template_path, car_config_path)
 
        if os.path.exists(train_app_path) and not overwrite:
            print('Train already exists. Delete it and rerun createcar to replace.')
        else:
            print("Copying train script. Adjust these before starting your car.")
            shutil.copyfile(train_template_path, train_app_path)

        if not os.path.exists(mycar_config_path):
            print("Copying my car config overrides")
            shutil.copyfile(myconfig_template_path, mycar_config_path)
            #now copy file contents from config to myconfig, with all lines commented out.
            cfg = open(car_config_path, "rt")
            mcfg = open(mycar_config_path, "at")
            copy = False
            for line in cfg:
                if "import os" in line:
                    copy = True
                if copy: 
                    mcfg.write("# " + line)
            cfg.close()
            mcfg.close()

 
        print("Donkey setup complete.")


class UpdateCar(BaseCommand):
    '''
    always run in the base ~/mycar dir to get latest
    '''

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='update', usage='%(prog)s [options]')
        parsed_args = parser.parse_args(args)
        return parsed_args
        
    def run(self, args):
        cc = CreateCar()
        cc.create_car(path=".", overwrite=True)
        

class FindCar(BaseCommand):
    def parse_args(self, args):
        pass        

        
    def run(self, args):
        print('Looking up your computer IP address...')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0] 
        print('Your IP address: %s ' %s.getsockname()[0])
        s.close()
        
        print("Finding your car's IP address...")
        cmd = "sudo nmap -sP " + ip + "/24 | awk '/^Nmap/{ip=$NF}/B8:27:EB/{print ip}'"
        print("Your car's ip address is:" )
        os.system(cmd)
        
        
        
class CalibrateCar(BaseCommand):    
    
    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='calibrate', usage='%(prog)s [options]')
        parser.add_argument('--channel', help="The channel you'd like to calibrate [0-15]")
        parser.add_argument('--address', default='0x40', help="The i2c address you'd like to calibrate [default 0x40]")
        parser.add_argument('--bus', default=None, help="The i2c bus you'd like to calibrate [default autodetect]")
        parser.add_argument('--pwmFreq', default=60, help="The frequency to use for the PWM")
        parser.add_argument('--arduino', dest='arduino', action='store_true', help='Use arduino pin for PWM (calibrate pin=<channel>)')
        parser.set_defaults(arduino=False)
        parsed_args = parser.parse_args(args)
        return parsed_args

    def run(self, args):
        args = self.parse_args(args)
        channel = int(args.channel)

        if args.arduino == True:
            from donkeycar.parts.actuator import ArduinoFirmata

            arduino_controller = ArduinoFirmata(servo_pin=channel)
            print('init Arduino PWM on pin %d' %(channel))
            input_prompt = "Enter a PWM setting to test ('q' for quit) (0-180): "
        else:
            from donkeycar.parts.actuator import PCA9685
            from donkeycar.parts.sombrero import Sombrero

            s = Sombrero()

            busnum = None
            if args.bus:
                busnum = int(args.bus)
            address = int(args.address, 16)
            print('init PCA9685 on channel %d address %s bus %s' %(channel, str(hex(address)), str(busnum)))
            freq = int(args.pwmFreq)
            print("Using PWM freq: {}".format(freq))
            c = PCA9685(channel, address=address, busnum=busnum, frequency=freq)
            input_prompt = "Enter a PWM setting to test ('q' for quit) (0-1500): "
            print()
        while True:
            try:
                val = input(input_prompt)
                if val == 'q' or val == 'Q':
                    break
                pmw = int(val)
                if args.arduino == True:
                    arduino_controller.set_pulse(channel,pmw)
                else:
                    c.run(pmw)
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt received, exit.")
                break
            except Exception as ex:
                print("Oops, {}".format(ex))


class MakeMovieShell(BaseCommand):
    '''
    take the make movie args and then call make movie command
    with lazy imports
    '''
    def __init__(self):
        self.deg_to_rad = math.pi / 180.0

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='makemovie')
        parser.add_argument('--tub', help='The tub to make movie from')
        parser.add_argument('--out', default='tub_movie.mp4', help='The movie filename to create. default: tub_movie.mp4')
        parser.add_argument('--config', default='./config.py', help='location of config file to use. default: ./config.py')
        parser.add_argument('--model', default=None, help='the model to use to show control outputs')
        parser.add_argument('--type', default=None, help='the model type to load')
        parser.add_argument('--salient', action="store_true", help='should we overlay salient map showing activations')
        parser.add_argument('--start', type=int, default=0, help='first frame to process')
        parser.add_argument('--end', type=int, default=-1, help='last frame to process')
        parser.add_argument('--scale', type=int, default=2, help='make image frame output larger by X mult')
        parsed_args = parser.parse_args(args)
        return parsed_args, parser

    def run(self, args):
        '''
        Load the images from a tub and create a movie from them.
        Movie
        '''
        args, parser = self.parse_args(args)

        from donkeycar.management.makemovie import MakeMovie

        mm = MakeMovie()
        mm.run(args, parser)


class TubCheck(BaseCommand):
    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubcheck', usage='%(prog)s [options]')
        parser.add_argument('tubs', nargs='+', help='paths to tubs')
        parser.add_argument('--fix', action='store_true', help='remove problem records')
        parser.add_argument('--delete_empty', action='store_true', help='delete tub dir with no records')
        parsed_args = parser.parse_args(args)
        return parsed_args

    def check(self, tub_paths, fix=False, delete_empty=False):
        '''
        Check for any problems. Looks at tubs and find problems in any records or images that won't open.
        If fix is True, then delete images and records that cause problems.
        '''
        cfg = load_config('config.py')
        tubs = gather_tubs(cfg, tub_paths)

        for tub in tubs:
            tub.check(fix=fix)
            if delete_empty and tub.get_num_records() == 0:
                import shutil
                print("removing empty tub", tub.path)
                shutil.rmtree(tub.path)

    def run(self, args):
        args = self.parse_args(args)
        self.check(args.tubs, args.fix, args.delete_empty)


class ShowHistogram(BaseCommand):

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubhist', usage='%(prog)s [options]')
        parser.add_argument('--tub', nargs='+', help='paths to tubs')
        parser.add_argument('--record', default=None, help='name of record to create histogram')
        parsed_args = parser.parse_args(args)
        return parsed_args

    def show_histogram(self, tub_paths, record_name):
        '''
        Produce a histogram of record type frequency in the given tub
        '''
        from matplotlib import pyplot as plt
        from donkeycar.parts.datastore import TubGroup

        tg = TubGroup(tub_paths=tub_paths)
        if record_name is not None:
            tg.df[record_name].hist(bins=50)
        else:
            tg.df.hist(bins=50)

        try:
            filename = os.path.basename(tub_paths) + '_hist_%s.png' % record_name.replace('/', '_')
            plt.savefig(filename)
            print('saving image to:', filename)
        except:
            pass
        plt.show()

    def run(self, args):
        args = self.parse_args(args)
        args.tub = ','.join(args.tub)
        self.show_histogram(args.tub, args.record)

class ShowTrack0(BaseCommand):

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubhist', usage='%(prog)s [options]')
        parser.add_argument('--tub', nargs='+', help='paths to tubs')
        parser.add_argument('--record', default=None, help='name of record to create histogram')
        parsed_args = parser.parse_args(args)
        return parsed_args

    def show_histogram(self, tub_paths, record_name):
        '''
        Produce a histogram of record type frequency in the given tub
        '''
        from matplotlib import pyplot as plt
        from donkeycar.parts.datastore import TubGroup

        print("****************************************")
        print("tub_paths:   ", tub_paths)
        print("record_name: ", record_name)
        print("****************************************")
        
        tg = TubGroup(tub_paths=tub_paths)
        if record_name is not None:
            tg.df[record_name].hist(bins=50)
        else:
            tg.df.hist(bins=50)

        print("tg:         ",tg)

        try:
            filename = os.path.basename(tub_paths) + '_hist_%s.png' % record_name.replace('/', '_')
            plt.savefig(filename)
            print('saving image to:', filename)
        except:
            pass
        plt.show()

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubhist', usage='%(prog)s [options]')
        parser.add_argument('--tub', nargs='+', help='paths to tubs')
        parser.add_argument('--record', default=None, help='name of record to create histogram')
        parsed_args = parser.parse_args(args)
        return parsed_args


    def run(self, args):
        args = self.parse_args(args)
        args.tub = ','.join(args.tub)
        self.show_histogram(args.tub, args.record)

class ShowTrack(BaseCommand):

    def plot_tracks(self, cfg, tub_paths, limit):
        '''
        Plot track data from tubs.

        usage

        donkey tubtrack --tub data/tub_33_20-04-16 --config ./myconfig.py
        

        '''
        import matplotlib.pyplot as plt
        import pandas as pd

        records = gather_records(cfg, tub_paths)
        user_angles = []
        user_throttles = []
        pilot_angles = []
        pilot_throttles = []       

        pos_speeds = []
        pos_pos_xs = []
        pos_pos_ys = []
        pos_pos_zs = []
        pos_ctes   = []

        records = records[:limit]
        num_records = len(records)
        print('processing %d records:' % num_records)

        for record_path in records:
            with open(record_path, 'r') as fp:
                record = json.load(fp)
            user_angle = float(record["user/angle"])
            user_throttle = float(record["user/throttle"])
            
            user_angles.append(user_angle)
            user_throttles.append(user_throttle)
            
            pos_speed = float(record["pos/speed"])
            pos_pos_x = float(record["pos/pos_x"])
            pos_pos_y = float(record["pos/pos_y"])
            pos_pos_z = float(record["pos/pos_z"])
            pos_cte   = float(record["pos/cte"])

            pos_pos_xs.append(pos_pos_x)
            pos_pos_ys.append(pos_pos_y)
            pos_pos_zs.append(pos_pos_z)
            pos_speeds.append(pos_speed)
            pos_ctes.append(pos_cte)
            
        angles_df = pd.DataFrame({'user_angle': user_angles, 'pilot_angle': user_angles})
        throttles_df = pd.DataFrame({'user_throttle': user_throttles, 'pilot_throttle': user_throttles})

        tracks_df = pd.DataFrame({'pos_x': pos_pos_xs, 'pos_z': pos_pos_zs})
        speeds_df = pd.DataFrame({'pos_speeds': pos_speeds, 'pos_ctes': pos_ctes})

        fig = plt.figure()

        title = "Parking Lot Nerds - Track Plot"
        fig.suptitle(title)

        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)

        #angles_df.plot(ax=ax1)
        #throttles_df.plot(ax=ax2)
        tracks_df.plot(ax=ax1)
        #tracks_df.plot(ax=ax2)
        speeds_df.plot(ax=ax2)

        ax1.legend(loc=4)
        ax2.legend(loc=4)
        
        plt.savefig('rainer'+ '_pred.png')
        plt.show()

        # Create data
        N = 500
        x = np.random.rand(N)
        y = np.random.rand(N)
        colors = (0,0,0)
        area = np.pi*3

        # Plot
        #plt.scatter(pos_pos_xs, pos_pos_zs, c=colors, alpha=0.5)
        plt.scatter(pos_pos_xs, pos_pos_zs, s=30, c=pos_speeds)
        
        plt.plot(pos_pos_xs, pos_pos_zs, c=colors, alpha=0.5)
        plt.xlim(-20,100)
        plt.ylim(-20,100)
        
        plt.title('Parking Lot Nerds - Recorded Tracks')
        plt.xlabel('x')
        plt.ylabel('z')
        plt.legend()
        
        plt.show()

    def run(self, args):
        args = self.parse_args(args)
        args.tub = ','.join(args.tub)
        cfg = load_config(args.config)
        self.plot_tracks(cfg, args.tub, args.limit)

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubhist', usage='%(prog)s [options]')
        parser.add_argument('--tub', nargs='+', help='paths to tubs')
        parser.add_argument('--config', default='./config.py', help='location of config file to use. default: ./config.py')
        parser.add_argument('--limit', default=10000, help='how many records to process')
        parsed_args = parser.parse_args(args)
        return parsed_args
   
class ConvertTrack(BaseCommand):

    def convert_tracks(self, cfg, tub_paths, limit):
        '''
        Convert AI driven track data from tubs to training data.

        usage

        donkey convtrack --tub data/tub_48_20-04-16 --config ./myconfig.py
        

        '''
        import matplotlib.pyplot as plt
        import pandas as pd

        records = gather_records(cfg, tub_paths)

        records = records[:limit]
        num_records = len(records)
        print('processing %d records:' % num_records)
        print('tub_paths: ', tub_paths)

        ix = 0
        for record_path in records:
            # increment json file number counter
            ix +=1

            #print(record_path) # name of json file
            # read AI record
            with open(record_path, 'r') as fp:
                record = json.load(fp)
            #user_angle = float(record["user/angle"])
            #user_throttle = float(record["user/throttle"])
            pilot_angle = float(record["pilot/angle"])
            pilot_throttle = float(record["pilot/throttle"])
                        
            # store pilot/angle into user/angle 
            record["user/angle"]      = pilot_angle
            record["user/throttle"]   = pilot_throttle
            record["pilot/angle"]     = 0.0
            record["pilot/throttle"]  = 0.0

            # write modified record
            myoutput_path = "./data/AI_tub_48_20-04-16/record_"+str(ix)+".json"          
            try:
                with open(myoutput_path, 'w') as fp:
                    json.dump(record, fp)
                    #print('wrote record:', record)
            except TypeError:
                print('troubles with record:', json_data)
            except FileNotFoundError:
                raise
            except:
                print("Unexpected error:", sys.exc_info()[0])
                raise
            
class FlipHub(BaseCommand):

    def flip_hub(self, cfg, tub_paths, tub_out):
        '''
        Convert AI driven track data from tubs to training data.

        usage

        (sds) rainer@neuron:~/mysim_ottawa$ 
        donkey fliphub --tub data/tub_10_20-04-15 --config ./myconfig.py --out data/flipped/tub_10_20-04-15


        '''
        import matplotlib.pyplot as plt
        import pandas as pd

        records = gather_records(cfg, tub_paths)
        num_records = len(records)

        print('processing %d records:' % num_records)
        print('input  --> tub_paths: ', tub_paths)
        print('output --> tub_out  : ', tub_out)
        #print('records: ', records)
        
        try:
            os.makedirs(tub_out)
        except FileExistsError:
            # directory already exists
            pass

        ix = 0
        for record_path in records:
            # increment json file number counter
            ix +=1

            #print("record_path: ",record_path) # name of json file
            
            # read unflipped json record
            with open(record_path, 'r') as fp:
                record = json.load(fp)
            user_angle = float(record["user/angle"])

            # read unflipped image
            image_filename = record["cam/image_array"]
            img_path = tub_paths+"/"+image_filename
            image = cv2.imread(img_path)
            img_arr = img_to_arr(image)
            
            # flip image
            image_fl = cv2.flip(img_arr, 1)

            # store pilot/angle into user/angle 
            record["user/angle"] = -user_angle
            
            # write flipped record & image
            myoutput_path = tub_out+"/record_"+str(ix)+".json"          
            myimageout    = tub_out+"/"+str(ix)+"_cam-image_array_.jpg"
            
            cv2.imwrite(myimageout, image_fl) 

            try:
                with open(myoutput_path, 'w') as fp:
                    json.dump(record, fp)
                    #print('wrote record:', record)
            except TypeError:
                print('troubles with record:', json_data)
            except FileNotFoundError:
                raise
            except:
                print("Unexpected error:", sys.exc_info()[0])
                raise
            


# t = create_sample_tub(tub_path, records=initial_records)

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubplot', usage='%(prog)s [options]')
        parser.add_argument('--tub', nargs='+', help='paths to tubs')
        parser.add_argument('--config', default='./config.py', help='location of config file to use. default: ./config.py')
        parser.add_argument('--out', default='data/flipped/', help='output tub path default: data/flipped/')
        parsed_args = parser.parse_args(args)
        return parsed_args

    def run(self, args):
        args = self.parse_args(args)
        args.tub = ','.join(args.tub)
        #args.out = args.tub+'/flipped'
        cfg = load_config(args.config)
        self.flip_hub(cfg, args.tub, args.out)

class ConSync(BaseCommand):
    '''
    continuously rsync data
    '''
    
    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='consync', usage='%(prog)s [options]')
        parser.add_argument('--dir', default='./cont_data/', help='paths to tubs')
        parser.add_argument('--delete', default='y', help='remove files locally that were deleted remotely y=yes n=no')
        parsed_args = parser.parse_args(args)
        return parsed_args

    def run(self, args):
        args = self.parse_args(args)
        cfg = load_config('config.py')
        dest_dir = args.dir
        del_arg = ""

        if args.delete == 'y':
            reply = input('WARNING:this rsync operation will delete data in the target dir: %s. ok to proceeed? [y/N]: ' % dest_dir)

            if reply != 'y' and reply != "Y":
                return
            del_arg = "--delete"

        if not dest_dir[-1] == '/' and not dest_dir[-1] == '\\':
            print("Desination dir should end with a /")
            return

        try:
            os.mkdir(dest_dir)
        except:
            pass

        while True:
            command = "rsync -aW --progress %s@%s:%s/data/ %s %s" %\
                (cfg.PI_USERNAME, cfg.PI_HOSTNAME, cfg.PI_DONKEY_ROOT, dest_dir, del_arg)

            os.system(command)
            time.sleep(5)

class ConTrain(BaseCommand):
    '''
    continuously train data
    '''
    
    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='contrain', usage='%(prog)s [options]')
        parser.add_argument('--tub', default='./cont_data/*', help='paths to tubs')
        parser.add_argument('--model', default='./models/drive.h5', help='path to model')
        parser.add_argument('--transfer', default=None, help='path to transfer model')
        parser.add_argument('--type', default='categorical', help='type of model (linear|categorical|rnn|imu|behavior|3d)')
        parser.add_argument('--aug', action="store_true", help='perform image augmentation')        
        parsed_args = parser.parse_args(args)
        return parsed_args

    def run(self, args):
        args = self.parse_args(args)
        cfg = load_config('config.py')
        import sys
        sys.path.append('.')
        from train import multi_train
        continuous = True
        multi_train(cfg, args.tub, args.model, args.transfer, args.type, continuous, args.aug)


class ShowCnnActivations(BaseCommand):

    def __init__(self):
        import matplotlib.pyplot as plt
        self.plt = plt

    def get_activations(self, image_path, model_path, cfg):
        '''
        Extracts features from an image

        returns activations/features
        '''
        from tensorflow.python.keras.models import load_model, Model

        model_path = os.path.expanduser(model_path)
        image_path = os.path.expanduser(image_path)

        model = load_model(model_path, compile=False)
        image = load_scaled_image_arr(image_path, cfg)[None, ...]

        conv_layer_names = self.get_conv_layers(model)
        input_layer = model.get_layer(name='img_in').input
        activations = []      
        for conv_layer_name in conv_layer_names:
            output_layer = model.get_layer(name=conv_layer_name).output

            layer_model = Model(inputs=[input_layer], outputs=[output_layer])
            activations.append(layer_model.predict(image)[0])
        return activations

    def create_figure(self, activations):
        import math
        cols = 6

        for i, layer in enumerate(activations):
            fig = self.plt.figure()
            fig.suptitle('Layer {}'.format(i+1))

            print('layer {} shape: {}'.format(i+1, layer.shape))
            feature_maps = layer.shape[2]
            rows = math.ceil(feature_maps / cols)

            for j in range(feature_maps):
                self.plt.subplot(rows, cols, j + 1)

                self.plt.imshow(layer[:, :, j])
        
        self.plt.show()

    def get_conv_layers(self, model):
        conv_layers = []
        for layer in model.layers:
            if layer.__class__.__name__ == 'Conv2D':
                conv_layers.append(layer.name)
        return conv_layers

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='cnnactivations', usage='%(prog)s [options]')
        parser.add_argument('--image', help='path to image')
        parser.add_argument('--model', default=None, help='path to model')
        parser.add_argument('--config', default='./config.py', help='location of config file to use. default: ./config.py')
        
        parsed_args = parser.parse_args(args)
        return parsed_args

    def run(self, args):
        args = self.parse_args(args)
        cfg = load_config(args.config)
        activations = self.get_activations(args.image, args.model, cfg)
        self.create_figure(activations)


class ShowPredictionPlots(BaseCommand):

    def plot_predictions(self, cfg, tub_paths, model_path, limit, model_type):
        '''
        Plot model predictions for angle and throttle against data from tubs.

        '''
        import matplotlib.pyplot as plt
        import pandas as pd

        model_path = os.path.expanduser(model_path)
        model = dk.utils.get_model_by_type(model_type, cfg)
        # This just gets us the text for the plot title:
        if model_type is None:
            model_type = cfg.DEFAULT_MODEL_TYPE
        model.load(model_path)

        records = gather_records(cfg, tub_paths)
        user_angles = []
        user_throttles = []
        pilot_angles = []
        pilot_throttles = []       

        records = records[:limit]
        num_records = len(records)
        print('processing %d records:' % num_records)

        for record_path in records:
            with open(record_path, 'r') as fp:
                record = json.load(fp)
            img_filename = os.path.join(tub_paths, record['cam/image_array'])
            img = load_scaled_image_arr(img_filename, cfg)
            user_angle = float(record["user/angle"])
            user_throttle = float(record["user/throttle"])
            pilot_angle, pilot_throttle = model.run(img)

            user_angles.append(user_angle)
            user_throttles.append(user_throttle)
            pilot_angles.append(pilot_angle)
            pilot_throttles.append(pilot_throttle)

        angles_df = pd.DataFrame({'user_angle': user_angles, 'pilot_angle': pilot_angles})
        throttles_df = pd.DataFrame({'user_throttle': user_throttles, 'pilot_throttle': pilot_throttles})

        fig = plt.figure()

        title = "Model Predictions\nTubs: " + tub_paths + "\nModel: " + model_path + "\nType: " + model_type
        fig.suptitle(title)

        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)

        angles_df.plot(ax=ax1)
        throttles_df.plot(ax=ax2)

        ax1.legend(loc=4)
        ax2.legend(loc=4)

        plt.savefig(model_path + '_pred.png')
        plt.show()

    def parse_args(self, args):
        parser = argparse.ArgumentParser(prog='tubplot', usage='%(prog)s [options]')
        parser.add_argument('--tub', nargs='+', help='paths to tubs')
        parser.add_argument('--model', default=None, help='name of record to create histogram')
        parser.add_argument('--limit', default=1000, help='how many records to process')
        parser.add_argument('--type', default=None, help='model type')
        parser.add_argument('--config', default='./config.py', help='location of config file to use. default: ./config.py')
        parsed_args = parser.parse_args(args)
        return parsed_args

    def run(self, args):
        args = self.parse_args(args)
        args.tub = ','.join(args.tub)
        cfg = load_config(args.config)
        self.plot_predictions(cfg, args.tub, args.model, args.limit, args.type)
        

def execute_from_command_line():
    """
    This is the function linked to the "donkey" terminal command.
    """
    commands = {
            'createcar': CreateCar,
            'findcar': FindCar,
            'calibrate': CalibrateCar,
            'tubclean': TubManager,
            'tubhist': ShowHistogram,
            'tubtrack': ShowTrack,
            'convtrack': ConvertTrack,
            'fliphub': FlipHub,
            'tubplot': ShowPredictionPlots,
            'tubcheck': TubCheck,
            'makemovie': MakeMovieShell,            
            'createjs': CreateJoystick,
            'consync': ConSync,
            'contrain': ConTrain,
            'cnnactivations': ShowCnnActivations,
            'update': UpdateCar,
                }
    
    args = sys.argv[:]

    if len(args) > 1 and args[1] in commands.keys():
        command = commands[args[1]]
        c = command()
        c.run(args[2:])
    else:
        dk.utils.eprint('Usage: The available commands are:')
        dk.utils.eprint(list(commands.keys()))
        
    
if __name__ == "__main__":
    execute_from_command_line()
    