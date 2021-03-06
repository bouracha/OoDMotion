import numpy as np
import torch
from torch.autograd import Variable
from utils import data_utils
import numpy as np

import torch.nn as nn
import torch.nn.functional as F


def sen_loss(outputs, all_seq, dim_used, dct_n, inputs, cartesian=False, lambda_ = 0.01, KL=None, reconstructions=None, log_var=None):
    """

    :param outputs: N * (seq_len*dim_used_len)
    :param all_seq: N * seq_len * dim_full_len
    :param input_n:
    :param dim_used:
    :return:
    """
    n, seq_len, dim_full_len = all_seq.data.shape
    dim_used_len = len(dim_used)
    dim_used = np.array(dim_used)

    _, idct_m = data_utils.get_dct_matrix(seq_len)
    idct_m = Variable(torch.from_numpy(idct_m)).float().cuda()
    outputs_t = outputs.view(-1, dct_n).transpose(0, 1)

    if cartesian:
        pred_cart = torch.matmul(idct_m[:, :dct_n], outputs_t).transpose(0, 1).contiguous()
        pred_cart = pred_cart.view(-1, dim_used_len, seq_len).transpose(1, 2).contiguous().view(-1, 3)
        targ_cart= all_seq.clone()[:, :, dim_used].contiguous().view(-1, 3)
        joint_loss = torch.mean(torch.norm(targ_cart - pred_cart, 2, 1))
    else:
        pred_expmap = torch.matmul(idct_m[:, :dct_n], outputs_t).transpose(0, 1).contiguous().view(-1, dim_used_len, seq_len).transpose(1, 2)
        targ_expmap = all_seq.clone()[:, :, dim_used]
        joint_loss = torch.mean(torch.abs(pred_expmap - targ_expmap))

    if KL == None:
        neg_gauss_log_lik = torch.zeros(1)
        latent_loss = torch.zeros(1)
        loss = joint_loss
    else:
        latent_loss = torch.mean(KL)
        mse = torch.pow((reconstructions - inputs), 2)
        gauss_log_lik = -mse#0.5*(log_var + np.log(2*np.pi) + (mse/(1e-8 + torch.exp(log_var))))
        neg_gauss_log_lik = -torch.mean(torch.sum(gauss_log_lik, axis=(1, 2)))

        loss = joint_loss + lambda_*(neg_gauss_log_lik + latent_loss)

    return loss, joint_loss, neg_gauss_log_lik, latent_loss


def euler_error(outputs, all_seq, input_n, dim_used, dct_n):
    """

    :param outputs:
    :param all_seq:
    :param input_n:
    :param dim_used:
    :return:
    """
    n, seq_len, dim_full_len = all_seq.data.shape
    dim_used_len = len(dim_used)

    _, idct_m = data_utils.get_dct_matrix(seq_len)
    idct_m = Variable(torch.from_numpy(idct_m)).float().cuda()
    outputs_t = outputs.view(-1, dct_n).transpose(0, 1)
    outputs_exp = torch.matmul(idct_m[:, :dct_n], outputs_t).transpose(0, 1).contiguous().view(-1, dim_used_len,
                                                                                               seq_len).transpose(1, 2)
    pred_expmap = all_seq.clone()
    dim_used = np.array(dim_used)
    pred_expmap[:, :, dim_used] = outputs_exp

    pred_expmap = pred_expmap[:, input_n:, :].contiguous().view(-1, dim_full_len)
    targ_expmap = all_seq[:, input_n:, :].clone().contiguous().view(-1, dim_full_len)

    # pred_expmap[:, 0:6] = 0
    # targ_expmap[:, 0:6] = 0
    pred_expmap = pred_expmap.view(-1, 3)
    targ_expmap = targ_expmap.view(-1, 3)

    pred_eul = data_utils.rotmat2euler_torch(data_utils.expmap2rotmat_torch(pred_expmap))
    pred_eul = pred_eul.view(-1, dim_full_len)

    targ_eul = data_utils.rotmat2euler_torch(data_utils.expmap2rotmat_torch(targ_expmap))
    targ_eul = targ_eul.view(-1, dim_full_len)
    mean_errors = torch.mean(torch.norm(pred_eul - targ_eul, 2, 1))

    return mean_errors


def mpjpe_error(outputs, all_seq, input_n, dim_used, dct_n):
    """

    :param outputs:
    :param all_seq:
    :param input_n:
    :param dim_used:
    :param data_mean:
    :param data_std:
    :return:
    """
    n, seq_len, dim_full_len = all_seq.data.shape
    dim_used_len = len(dim_used)

    _, idct_m = data_utils.get_dct_matrix(seq_len)
    idct_m = Variable(torch.from_numpy(idct_m)).float().cuda()
    outputs_t = outputs.view(-1, dct_n).transpose(0, 1)
    outputs_exp = torch.matmul(idct_m[:, :dct_n], outputs_t).transpose(0, 1).contiguous().view(-1, dim_used_len,
                                                                                               seq_len).transpose(1, 2)
    pred_expmap = all_seq.clone()
    dim_used = np.array(dim_used)
    pred_expmap[:, :, dim_used] = outputs_exp
    pred_expmap = pred_expmap[:, input_n:, :].contiguous().view(-1, dim_full_len).clone()
    targ_expmap = all_seq[:, input_n:, :].clone().contiguous().view(-1, dim_full_len)

    pred_expmap[:, 0:6] = 0
    targ_expmap[:, 0:6] = 0

    targ_p3d = data_utils.expmap2xyz_torch(targ_expmap).view(-1, 3)

    pred_p3d = data_utils.expmap2xyz_torch(pred_expmap).view(-1, 3)

    mean_3d_err = torch.mean(torch.norm(targ_p3d - pred_p3d, 2, 1))

    return mean_3d_err


def mpjpe_error_cmu(outputs, all_seq, input_n, dim_used, dct_n):
    n, seq_len, dim_full_len = all_seq.data.shape
    dim_used_len = len(dim_used)

    _, idct_m = data_utils.get_dct_matrix(seq_len)
    idct_m = Variable(torch.from_numpy(idct_m)).float().cuda()
    outputs_t = outputs.view(-1, dct_n).transpose(0, 1)
    outputs_exp = torch.matmul(idct_m[:, :dct_n], outputs_t).transpose(0, 1).contiguous().view(-1, dim_used_len,
                                                                                               seq_len).transpose(1, 2)
    pred_expmap = all_seq.clone()
    dim_used = np.array(dim_used)
    pred_expmap[:, :, dim_used] = outputs_exp
    pred_expmap = pred_expmap[:, input_n:, :].contiguous().view(-1, dim_full_len)
    targ_expmap = all_seq[:, input_n:, :].clone().contiguous().view(-1, dim_full_len)
    pred_expmap[:, 0:6] = 0
    targ_expmap[:, 0:6] = 0

    targ_p3d = data_utils.expmap2xyz_torch_cmu(targ_expmap).view(-1, 3)
    pred_p3d = data_utils.expmap2xyz_torch_cmu(pred_expmap).view(-1, 3)

    mean_3d_err = torch.mean(torch.norm(targ_p3d - pred_p3d, 2, 1))

    return mean_3d_err


def mpjpe_error_p3d(outputs, all_seq, dct_n, dim_used):
    """

    :param outputs:n*66*dct_n
    :param all_seq:
    :param dct_n:
    :param dim_used:
    :return:
    """
    n, seq_len, dim_full_len = all_seq.data.shape
    dim_used = np.array(dim_used)
    dim_used_len = len(dim_used)

    _, idct_m = data_utils.get_dct_matrix(seq_len)
    idct_m = Variable(torch.from_numpy(idct_m)).float().cuda()
    outputs_t = outputs.view(-1, dct_n).transpose(0, 1)
    outputs_p3d = torch.matmul(idct_m[:, 0:dct_n], outputs_t).transpose(0, 1).contiguous().view(-1, dim_used_len,
                                                                                                seq_len).transpose(1,
                                                                                                                   2)
    pred_3d = outputs_p3d.contiguous().view(-1, dim_used_len).view(-1, 3)
    targ_3d = all_seq[:, :, dim_used].contiguous().view(-1, dim_used_len).view(-1, 3)

    mean_3d_err = torch.mean(torch.norm(pred_3d - targ_3d, 2, 1))

    return mean_3d_err


def mpjpe_error_3dpw(outputs, all_seq, dct_n, dim_used):
    n, seq_len, dim_full_len = all_seq.data.shape

    _, idct_m = data_utils.get_dct_matrix(seq_len)
    idct_m = Variable(torch.from_numpy(idct_m)).float().cuda()
    outputs_t = outputs.view(-1, dct_n).transpose(0, 1)
    outputs_exp = torch.matmul(idct_m[:, 0:dct_n], outputs_t).transpose(0, 1).contiguous().view(-1, dim_full_len - 3,
                                                                                                seq_len).transpose(1,
                                                                                                                   2)
    pred_3d = all_seq.clone()
    pred_3d[:, :, dim_used] = outputs_exp
    pred_3d = pred_3d.contiguous().view(-1, dim_full_len).view(-1, 3)
    targ_3d = all_seq.contiguous().view(-1, dim_full_len).view(-1, 3)

    mean_3d_err = torch.mean(torch.norm(pred_3d - targ_3d, 2, 1))

    return mean_3d_err
