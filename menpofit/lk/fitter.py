from __future__ import division
from menpo.feature import no_op
from menpofit.transform import DifferentiableAlignmentAffine
from menpofit.fitter import MultiFitter, noisy_target_alignment_transform
from menpofit import checks
from .algorithm import IC
from .residual import SSD, FourierSSD
from .result import LKFitterResult


# TODO: document me!
class LKFitter(MultiFitter):
    r"""
    """
    def __init__(self, template, group=None, label=None, features=no_op,
                 transform_cls=DifferentiableAlignmentAffine, diagonal=None,
                 scales=(1, .5), scale_features=True, algorithm_cls=IC,
                 residual_cls=SSD, **kwargs):
        # check parameters
        checks.check_diagonal(diagonal)
        scales, n_levels = checks.check_scales(scales)
        features = checks.check_features(features, n_levels)
        scale_features = checks.check_scale_features(scale_features, features)
        # set parameters
        self.features = features
        self.transform_cls = transform_cls
        self.diagonal = diagonal
        self.scales = list(scales)
        self.scales.reverse()
        self.scale_features = scale_features

        self.templates, self.sources = self._prepare_template(
            template, group=group, label=label)

        self.reference_shape = self.sources[0]

        self.algorithms = []
        for j, (t, s) in enumerate(zip(self.templates, self.sources)):
            transform = self.transform_cls(s, s)
            if ('kernel_func' in kwargs and
                (residual_cls is SSD or
                 residual_cls is FourierSSD)):
                kernel_func = kwargs.pop('kernel_func')
                kernel = kernel_func(t.shape)
                residual = residual_cls(kernel=kernel)
            else:
                residual = residual_cls()
            algorithm = algorithm_cls(t, transform, residual, **kwargs)
            self.algorithms.append(algorithm)

    def _prepare_template(self, template, group=None, label=None):
        template = template.crop_to_landmarks(group=group, label=label)
        template = template.as_masked()

        # rescale template to diagonal range
        if self.diagonal:
            template = template.rescale_landmarks_to_diagonal_range(
                self.diagonal, group=group, label=label)

        # obtain image representation
        from copy import deepcopy
        scales = deepcopy(self.scales)
        scales.reverse()
        templates = []
        for j, s in enumerate(scales):
            if j == 0:
                # compute features at highest level
                feature_template = self.features[j](template)
            elif self.scale_features:
                # scale features at other levels
                feature_template = templates[0].rescale(s)
            else:
                # scale image and compute features at other levels
                scaled_template = template.rescale(s)
                feature_template = self.features[j](scaled_template)
            templates.append(feature_template)
        templates.reverse()

        # get sources per level
        sources = [i.landmarks[group][label] for i in templates]

        return templates, sources

    def noisy_shape_from_shape(self, gt_shape, noise_std=0.04):
        transform = noisy_target_alignment_transform(
            self.transform_cls, self.reference_shape, gt_shape,
            noise_std=noise_std)
        return transform.apply(self.reference_shape)

    def _fitter_result(self, image, algorithm_results, affine_correction,
                       gt_shape=None):
        return LKFitterResult(image, self, algorithm_results,
                              affine_correction, gt_shape=gt_shape)