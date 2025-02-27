import os

import numpy as np

import settings
from utils import add_caffe_to_path

def def_FeatureExtractor(caffe):
    class FeatureExtractor(caffe.Net):
        """
        FeatureExtractor extends Net for to provide a simple interface for
        extracting features.

        Parameters
        ----------
        mean, input_scale, raw_scale, channel_swap: params for
            preprocessing options.
        """

        def __init__(self, model_file, pretrained_file, image_dims, mean=None,
                     input_scale=None, raw_scale=None, channel_swap=None):
            caffe.Net.__init__(self, model_file, pretrained_file, caffe.TEST)

            # configure pre-processing
            in_ = self.inputs[0]
            self.transformer = caffe.io.Transformer(
                {in_: self.blobs[in_].data.shape})
            self.transformer.set_transpose(in_, (2, 0, 1))
            if mean is not None:
                self.transformer.set_mean(in_, mean)
            if input_scale is not None:
                self.transformer.set_input_scale(in_, input_scale)
            if raw_scale is not None:
                self.transformer.set_raw_scale(in_, raw_scale)
            if channel_swap is not None:
                self.transformer.set_channel_swap(in_, channel_swap)

            self.image_dims = image_dims

        def preprocess_inputs(self, inputs, auto_reshape=True):
            """
            Preprocesses inputs.

            Parameters
            ----------
            inputs : iterable of (H x W x K) input ndarrays.

            Returns
            -------
            caffe_in: Preprocessed input which can be passed to forward.
            """
            # Only auto reshape if we don't set the image dimensions explicitly
            if auto_reshape and self.image_dims is None:
                # Keep original input dimensions and reshape the net
                # All inputs should have the same input dimensions!
                input_ = np.zeros(
                    (len(inputs), ) + inputs[0].shape,
                    dtype=np.float32
                )
                for ix, in_ in enumerate(inputs):
                    input_[ix] = in_
            else:
                # Scale to standardize input dimensions.
                input_ = np.zeros(
                    (len(inputs), self.image_dims[0], self.image_dims[1],
                    inputs[0].shape[2]),
                    dtype=np.float32
                )
                for ix, in_ in enumerate(inputs):
                    input_[ix] = caffe.io.resize_image(in_, self.image_dims)

            # Run net
            caffe_in = np.zeros(
                np.array(input_.shape)[[0, 3, 1, 2]],
                dtype=np.float32
            )
            if auto_reshape:
                self.reshape_by_input(caffe_in)

            for ix, in_ in enumerate(input_):
                caffe_in[ix] = self.transformer.preprocess(self.inputs[0], in_)

            return caffe_in

        def reshape_by_input(self, caffe_in):
            """
            Reshapes the whole net according to the input
            """
            in_ = self.inputs[0]
            if tuple(self.blobs[in_].data.shape)!=tuple(caffe_in.shape):
              print 'Reshaping net to {} input size...'.format(caffe_in.shape)
              self.blobs[in_].reshape(*caffe_in.shape)
              self.transformer.inputs = {in_: self.blobs[in_].data.shape}
              self.reshape()

        def predict(self, filename, auto_reshape=True):
            if isinstance(filename, list) or isinstance(filename, tuple):
                inputs = [caffe.io.load_image(x) for x in filename]
            elif isinstance(filename, np.ndarray):
                inputs = [filename]
            else:
                inputs = [caffe.io.load_image(filename)]
            # Each member of inputs is H x W x 3 in the range [0,1]

            #print 'inputs[0].shape',inputs[0].shape, inputs[0].min(), inputs[0].mean(), inputs[0].max()
            caffe_in = self.preprocess_inputs(inputs, auto_reshape=auto_reshape)
            # caffe_in is N x 3 x H x W in the range [-lo,+hi] where lo,hi are ~ -100,+100
            #print 'caffe_in', caffe_in.shape, caffe_in.min(), caffe_in.mean(), caffe_in.max()
            return self.forward_all(**{self.inputs[0]: caffe_in})

        def extract_features(self, filename, blob_names, auto_reshape=True):
            # sanity checking
            if len(set(blob_names)) != len(blob_names):
                raise ValueError("Duplicate name in blob_names: %s" % blob_names)

            self.predict(filename, auto_reshape=auto_reshape)
            ret = {}
            for blob_name in blob_names:
                blob_data = self.blobs[blob_name].data.copy()
                ret[blob_name] = blob_data

            return ret

        def get_input_blob(self):
            """
            Returns a deep copy of the input blob. Typically, this needs to be deprocessed.
            """
            in_ = self.inputs[0]
            return self.blobs[in_].data.copy()

    return FeatureExtractor


def load_fet_extractor(
    import_caffe,
    extractor,
    deployfile_relpath,
    weights_relpath,
    image_dims=(256, 256),
    mean=(104, 117, 123),
    device_id=0,
    input_scale=1,
):
    caffe=import_caffe()

    FeatureExtractor = extractor(caffe)

    mean = np.array(mean)

    model_file = os.path.join(settings.CAFFE_ROOT, deployfile_relpath)
    pretrained_file = os.path.join(settings.CAFFE_ROOT, weights_relpath)

    if settings.CAFFE_GPU:
        print 'Using GPU'
        caffe.set_mode_gpu()
        print 'Using device #{}'.format(device_id)
        caffe.set_device(device_id)
    else:
        print 'Using CPU'
        caffe.set_mode_cpu()

    net = FeatureExtractor(
        model_file=model_file,
        pretrained_file=pretrained_file,
        image_dims=image_dims,
        mean=mean,
        input_scale=input_scale,
        raw_scale=255,
        channel_swap=(2, 1, 0),
    )

    return caffe, net

