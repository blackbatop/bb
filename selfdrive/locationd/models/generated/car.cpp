#include "car.h"

namespace {
#define DIM 9
#define EDIM 9
#define MEDIM 9
typedef void (*Hfun)(double *, double *, double *);

double mass;

void set_mass(double x){ mass = x;}

double rotational_inertia;

void set_rotational_inertia(double x){ rotational_inertia = x;}

double center_to_front;

void set_center_to_front(double x){ center_to_front = x;}

double center_to_rear;

void set_center_to_rear(double x){ center_to_rear = x;}

double stiffness_front;

void set_stiffness_front(double x){ stiffness_front = x;}

double stiffness_rear;

void set_stiffness_rear(double x){ stiffness_rear = x;}
const static double MAHA_THRESH_25 = 3.8414588206941227;
const static double MAHA_THRESH_24 = 5.991464547107981;
const static double MAHA_THRESH_30 = 3.8414588206941227;
const static double MAHA_THRESH_26 = 3.8414588206941227;
const static double MAHA_THRESH_27 = 3.8414588206941227;
const static double MAHA_THRESH_29 = 3.8414588206941227;
const static double MAHA_THRESH_28 = 3.8414588206941227;
const static double MAHA_THRESH_31 = 3.8414588206941227;

/******************************************************************************
 *                       Code generated with SymPy 1.12                       *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_2366717911037962719) {
   out_2366717911037962719[0] = delta_x[0] + nom_x[0];
   out_2366717911037962719[1] = delta_x[1] + nom_x[1];
   out_2366717911037962719[2] = delta_x[2] + nom_x[2];
   out_2366717911037962719[3] = delta_x[3] + nom_x[3];
   out_2366717911037962719[4] = delta_x[4] + nom_x[4];
   out_2366717911037962719[5] = delta_x[5] + nom_x[5];
   out_2366717911037962719[6] = delta_x[6] + nom_x[6];
   out_2366717911037962719[7] = delta_x[7] + nom_x[7];
   out_2366717911037962719[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_70336108065318295) {
   out_70336108065318295[0] = -nom_x[0] + true_x[0];
   out_70336108065318295[1] = -nom_x[1] + true_x[1];
   out_70336108065318295[2] = -nom_x[2] + true_x[2];
   out_70336108065318295[3] = -nom_x[3] + true_x[3];
   out_70336108065318295[4] = -nom_x[4] + true_x[4];
   out_70336108065318295[5] = -nom_x[5] + true_x[5];
   out_70336108065318295[6] = -nom_x[6] + true_x[6];
   out_70336108065318295[7] = -nom_x[7] + true_x[7];
   out_70336108065318295[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_281700328218384173) {
   out_281700328218384173[0] = 1.0;
   out_281700328218384173[1] = 0;
   out_281700328218384173[2] = 0;
   out_281700328218384173[3] = 0;
   out_281700328218384173[4] = 0;
   out_281700328218384173[5] = 0;
   out_281700328218384173[6] = 0;
   out_281700328218384173[7] = 0;
   out_281700328218384173[8] = 0;
   out_281700328218384173[9] = 0;
   out_281700328218384173[10] = 1.0;
   out_281700328218384173[11] = 0;
   out_281700328218384173[12] = 0;
   out_281700328218384173[13] = 0;
   out_281700328218384173[14] = 0;
   out_281700328218384173[15] = 0;
   out_281700328218384173[16] = 0;
   out_281700328218384173[17] = 0;
   out_281700328218384173[18] = 0;
   out_281700328218384173[19] = 0;
   out_281700328218384173[20] = 1.0;
   out_281700328218384173[21] = 0;
   out_281700328218384173[22] = 0;
   out_281700328218384173[23] = 0;
   out_281700328218384173[24] = 0;
   out_281700328218384173[25] = 0;
   out_281700328218384173[26] = 0;
   out_281700328218384173[27] = 0;
   out_281700328218384173[28] = 0;
   out_281700328218384173[29] = 0;
   out_281700328218384173[30] = 1.0;
   out_281700328218384173[31] = 0;
   out_281700328218384173[32] = 0;
   out_281700328218384173[33] = 0;
   out_281700328218384173[34] = 0;
   out_281700328218384173[35] = 0;
   out_281700328218384173[36] = 0;
   out_281700328218384173[37] = 0;
   out_281700328218384173[38] = 0;
   out_281700328218384173[39] = 0;
   out_281700328218384173[40] = 1.0;
   out_281700328218384173[41] = 0;
   out_281700328218384173[42] = 0;
   out_281700328218384173[43] = 0;
   out_281700328218384173[44] = 0;
   out_281700328218384173[45] = 0;
   out_281700328218384173[46] = 0;
   out_281700328218384173[47] = 0;
   out_281700328218384173[48] = 0;
   out_281700328218384173[49] = 0;
   out_281700328218384173[50] = 1.0;
   out_281700328218384173[51] = 0;
   out_281700328218384173[52] = 0;
   out_281700328218384173[53] = 0;
   out_281700328218384173[54] = 0;
   out_281700328218384173[55] = 0;
   out_281700328218384173[56] = 0;
   out_281700328218384173[57] = 0;
   out_281700328218384173[58] = 0;
   out_281700328218384173[59] = 0;
   out_281700328218384173[60] = 1.0;
   out_281700328218384173[61] = 0;
   out_281700328218384173[62] = 0;
   out_281700328218384173[63] = 0;
   out_281700328218384173[64] = 0;
   out_281700328218384173[65] = 0;
   out_281700328218384173[66] = 0;
   out_281700328218384173[67] = 0;
   out_281700328218384173[68] = 0;
   out_281700328218384173[69] = 0;
   out_281700328218384173[70] = 1.0;
   out_281700328218384173[71] = 0;
   out_281700328218384173[72] = 0;
   out_281700328218384173[73] = 0;
   out_281700328218384173[74] = 0;
   out_281700328218384173[75] = 0;
   out_281700328218384173[76] = 0;
   out_281700328218384173[77] = 0;
   out_281700328218384173[78] = 0;
   out_281700328218384173[79] = 0;
   out_281700328218384173[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_3945758947465398650) {
   out_3945758947465398650[0] = state[0];
   out_3945758947465398650[1] = state[1];
   out_3945758947465398650[2] = state[2];
   out_3945758947465398650[3] = state[3];
   out_3945758947465398650[4] = state[4];
   out_3945758947465398650[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8000000000000007*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_3945758947465398650[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_3945758947465398650[7] = state[7];
   out_3945758947465398650[8] = state[8];
}
void F_fun(double *state, double dt, double *out_7239966002367196486) {
   out_7239966002367196486[0] = 1;
   out_7239966002367196486[1] = 0;
   out_7239966002367196486[2] = 0;
   out_7239966002367196486[3] = 0;
   out_7239966002367196486[4] = 0;
   out_7239966002367196486[5] = 0;
   out_7239966002367196486[6] = 0;
   out_7239966002367196486[7] = 0;
   out_7239966002367196486[8] = 0;
   out_7239966002367196486[9] = 0;
   out_7239966002367196486[10] = 1;
   out_7239966002367196486[11] = 0;
   out_7239966002367196486[12] = 0;
   out_7239966002367196486[13] = 0;
   out_7239966002367196486[14] = 0;
   out_7239966002367196486[15] = 0;
   out_7239966002367196486[16] = 0;
   out_7239966002367196486[17] = 0;
   out_7239966002367196486[18] = 0;
   out_7239966002367196486[19] = 0;
   out_7239966002367196486[20] = 1;
   out_7239966002367196486[21] = 0;
   out_7239966002367196486[22] = 0;
   out_7239966002367196486[23] = 0;
   out_7239966002367196486[24] = 0;
   out_7239966002367196486[25] = 0;
   out_7239966002367196486[26] = 0;
   out_7239966002367196486[27] = 0;
   out_7239966002367196486[28] = 0;
   out_7239966002367196486[29] = 0;
   out_7239966002367196486[30] = 1;
   out_7239966002367196486[31] = 0;
   out_7239966002367196486[32] = 0;
   out_7239966002367196486[33] = 0;
   out_7239966002367196486[34] = 0;
   out_7239966002367196486[35] = 0;
   out_7239966002367196486[36] = 0;
   out_7239966002367196486[37] = 0;
   out_7239966002367196486[38] = 0;
   out_7239966002367196486[39] = 0;
   out_7239966002367196486[40] = 1;
   out_7239966002367196486[41] = 0;
   out_7239966002367196486[42] = 0;
   out_7239966002367196486[43] = 0;
   out_7239966002367196486[44] = 0;
   out_7239966002367196486[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_7239966002367196486[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_7239966002367196486[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_7239966002367196486[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_7239966002367196486[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_7239966002367196486[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_7239966002367196486[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_7239966002367196486[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_7239966002367196486[53] = -9.8000000000000007*dt;
   out_7239966002367196486[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_7239966002367196486[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_7239966002367196486[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_7239966002367196486[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_7239966002367196486[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_7239966002367196486[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_7239966002367196486[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_7239966002367196486[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_7239966002367196486[62] = 0;
   out_7239966002367196486[63] = 0;
   out_7239966002367196486[64] = 0;
   out_7239966002367196486[65] = 0;
   out_7239966002367196486[66] = 0;
   out_7239966002367196486[67] = 0;
   out_7239966002367196486[68] = 0;
   out_7239966002367196486[69] = 0;
   out_7239966002367196486[70] = 1;
   out_7239966002367196486[71] = 0;
   out_7239966002367196486[72] = 0;
   out_7239966002367196486[73] = 0;
   out_7239966002367196486[74] = 0;
   out_7239966002367196486[75] = 0;
   out_7239966002367196486[76] = 0;
   out_7239966002367196486[77] = 0;
   out_7239966002367196486[78] = 0;
   out_7239966002367196486[79] = 0;
   out_7239966002367196486[80] = 1;
}
void h_25(double *state, double *unused, double *out_4414103654617947245) {
   out_4414103654617947245[0] = state[6];
}
void H_25(double *state, double *unused, double *out_1365985619853648806) {
   out_1365985619853648806[0] = 0;
   out_1365985619853648806[1] = 0;
   out_1365985619853648806[2] = 0;
   out_1365985619853648806[3] = 0;
   out_1365985619853648806[4] = 0;
   out_1365985619853648806[5] = 0;
   out_1365985619853648806[6] = 1;
   out_1365985619853648806[7] = 0;
   out_1365985619853648806[8] = 0;
}
void h_24(double *state, double *unused, double *out_218399050948173848) {
   out_218399050948173848[0] = state[4];
   out_218399050948173848[1] = state[5];
}
void H_24(double *state, double *unused, double *out_8020191077961834563) {
   out_8020191077961834563[0] = 0;
   out_8020191077961834563[1] = 0;
   out_8020191077961834563[2] = 0;
   out_8020191077961834563[3] = 0;
   out_8020191077961834563[4] = 1;
   out_8020191077961834563[5] = 0;
   out_8020191077961834563[6] = 0;
   out_8020191077961834563[7] = 0;
   out_8020191077961834563[8] = 0;
   out_8020191077961834563[9] = 0;
   out_8020191077961834563[10] = 0;
   out_8020191077961834563[11] = 0;
   out_8020191077961834563[12] = 0;
   out_8020191077961834563[13] = 0;
   out_8020191077961834563[14] = 1;
   out_8020191077961834563[15] = 0;
   out_8020191077961834563[16] = 0;
   out_8020191077961834563[17] = 0;
}
void h_30(double *state, double *unused, double *out_7444812492615309208) {
   out_7444812492615309208[0] = state[4];
}
void H_30(double *state, double *unused, double *out_1236646672710408736) {
   out_1236646672710408736[0] = 0;
   out_1236646672710408736[1] = 0;
   out_1236646672710408736[2] = 0;
   out_1236646672710408736[3] = 0;
   out_1236646672710408736[4] = 1;
   out_1236646672710408736[5] = 0;
   out_1236646672710408736[6] = 0;
   out_1236646672710408736[7] = 0;
   out_1236646672710408736[8] = 0;
}
void h_26(double *state, double *unused, double *out_442049788822243429) {
   out_442049788822243429[0] = state[7];
}
void H_26(double *state, double *unused, double *out_2375517699020407418) {
   out_2375517699020407418[0] = 0;
   out_2375517699020407418[1] = 0;
   out_2375517699020407418[2] = 0;
   out_2375517699020407418[3] = 0;
   out_2375517699020407418[4] = 0;
   out_2375517699020407418[5] = 0;
   out_2375517699020407418[6] = 0;
   out_2375517699020407418[7] = 1;
   out_2375517699020407418[8] = 0;
}
void h_27(double *state, double *unused, double *out_3470593801716284810) {
   out_3470593801716284810[0] = state[3];
}
void H_27(double *state, double *unused, double *out_938116639090016175) {
   out_938116639090016175[0] = 0;
   out_938116639090016175[1] = 0;
   out_938116639090016175[2] = 0;
   out_938116639090016175[3] = 1;
   out_938116639090016175[4] = 0;
   out_938116639090016175[5] = 0;
   out_938116639090016175[6] = 0;
   out_938116639090016175[7] = 0;
   out_938116639090016175[8] = 0;
}
void h_29(double *state, double *unused, double *out_7965145529649909723) {
   out_7965145529649909723[0] = state[1];
}
void H_29(double *state, double *unused, double *out_1746878017024800920) {
   out_1746878017024800920[0] = 0;
   out_1746878017024800920[1] = 1;
   out_1746878017024800920[2] = 0;
   out_1746878017024800920[3] = 0;
   out_1746878017024800920[4] = 0;
   out_1746878017024800920[5] = 0;
   out_1746878017024800920[6] = 0;
   out_1746878017024800920[7] = 0;
   out_1746878017024800920[8] = 0;
}
void h_28(double *state, double *unused, double *out_5501663824664413576) {
   out_5501663824664413576[0] = state[0];
}
void H_28(double *state, double *unused, double *out_3335521000044729654) {
   out_3335521000044729654[0] = 1;
   out_3335521000044729654[1] = 0;
   out_3335521000044729654[2] = 0;
   out_3335521000044729654[3] = 0;
   out_3335521000044729654[4] = 0;
   out_3335521000044729654[5] = 0;
   out_3335521000044729654[6] = 0;
   out_3335521000044729654[7] = 0;
   out_3335521000044729654[8] = 0;
}
void h_31(double *state, double *unused, double *out_5392762942373062487) {
   out_5392762942373062487[0] = state[8];
}
void H_31(double *state, double *unused, double *out_1396631581730609234) {
   out_1396631581730609234[0] = 0;
   out_1396631581730609234[1] = 0;
   out_1396631581730609234[2] = 0;
   out_1396631581730609234[3] = 0;
   out_1396631581730609234[4] = 0;
   out_1396631581730609234[5] = 0;
   out_1396631581730609234[6] = 0;
   out_1396631581730609234[7] = 0;
   out_1396631581730609234[8] = 1;
}
#include <eigen3/Eigen/Dense>
#include <iostream>

typedef Eigen::Matrix<double, DIM, DIM, Eigen::RowMajor> DDM;
typedef Eigen::Matrix<double, EDIM, EDIM, Eigen::RowMajor> EEM;
typedef Eigen::Matrix<double, DIM, EDIM, Eigen::RowMajor> DEM;

void predict(double *in_x, double *in_P, double *in_Q, double dt) {
  typedef Eigen::Matrix<double, MEDIM, MEDIM, Eigen::RowMajor> RRM;

  double nx[DIM] = {0};
  double in_F[EDIM*EDIM] = {0};

  // functions from sympy
  f_fun(in_x, dt, nx);
  F_fun(in_x, dt, in_F);


  EEM F(in_F);
  EEM P(in_P);
  EEM Q(in_Q);

  RRM F_main = F.topLeftCorner(MEDIM, MEDIM);
  P.topLeftCorner(MEDIM, MEDIM) = (F_main * P.topLeftCorner(MEDIM, MEDIM)) * F_main.transpose();
  P.topRightCorner(MEDIM, EDIM - MEDIM) = F_main * P.topRightCorner(MEDIM, EDIM - MEDIM);
  P.bottomLeftCorner(EDIM - MEDIM, MEDIM) = P.bottomLeftCorner(EDIM - MEDIM, MEDIM) * F_main.transpose();

  P = P + dt*Q;

  // copy out state
  memcpy(in_x, nx, DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
}

// note: extra_args dim only correct when null space projecting
// otherwise 1
template <int ZDIM, int EADIM, bool MAHA_TEST>
void update(double *in_x, double *in_P, Hfun h_fun, Hfun H_fun, Hfun Hea_fun, double *in_z, double *in_R, double *in_ea, double MAHA_THRESHOLD) {
  typedef Eigen::Matrix<double, ZDIM, ZDIM, Eigen::RowMajor> ZZM;
  typedef Eigen::Matrix<double, ZDIM, DIM, Eigen::RowMajor> ZDM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, EDIM, Eigen::RowMajor> XEM;
  //typedef Eigen::Matrix<double, EDIM, ZDIM, Eigen::RowMajor> EZM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, 1> X1M;
  typedef Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor> XXM;

  double in_hx[ZDIM] = {0};
  double in_H[ZDIM * DIM] = {0};
  double in_H_mod[EDIM * DIM] = {0};
  double delta_x[EDIM] = {0};
  double x_new[DIM] = {0};


  // state x, P
  Eigen::Matrix<double, ZDIM, 1> z(in_z);
  EEM P(in_P);
  ZZM pre_R(in_R);

  // functions from sympy
  h_fun(in_x, in_ea, in_hx);
  H_fun(in_x, in_ea, in_H);
  ZDM pre_H(in_H);

  // get y (y = z - hx)
  Eigen::Matrix<double, ZDIM, 1> pre_y(in_hx); pre_y = z - pre_y;
  X1M y; XXM H; XXM R;
  if (Hea_fun){
    typedef Eigen::Matrix<double, ZDIM, EADIM, Eigen::RowMajor> ZAM;
    double in_Hea[ZDIM * EADIM] = {0};
    Hea_fun(in_x, in_ea, in_Hea);
    ZAM Hea(in_Hea);
    XXM A = Hea.transpose().fullPivLu().kernel();


    y = A.transpose() * pre_y;
    H = A.transpose() * pre_H;
    R = A.transpose() * pre_R * A;
  } else {
    y = pre_y;
    H = pre_H;
    R = pre_R;
  }
  // get modified H
  H_mod_fun(in_x, in_H_mod);
  DEM H_mod(in_H_mod);
  XEM H_err = H * H_mod;

  // Do mahalobis distance test
  if (MAHA_TEST){
    XXM a = (H_err * P * H_err.transpose() + R).inverse();
    double maha_dist = y.transpose() * a * y;
    if (maha_dist > MAHA_THRESHOLD){
      R = 1.0e16 * R;
    }
  }

  // Outlier resilient weighting
  double weight = 1;//(1.5)/(1 + y.squaredNorm()/R.sum());

  // kalman gains and I_KH
  XXM S = ((H_err * P) * H_err.transpose()) + R/weight;
  XEM KT = S.fullPivLu().solve(H_err * P.transpose());
  //EZM K = KT.transpose(); TODO: WHY DOES THIS NOT COMPILE?
  //EZM K = S.fullPivLu().solve(H_err * P.transpose()).transpose();
  //std::cout << "Here is the matrix rot:\n" << K << std::endl;
  EEM I_KH = Eigen::Matrix<double, EDIM, EDIM>::Identity() - (KT.transpose() * H_err);

  // update state by injecting dx
  Eigen::Matrix<double, EDIM, 1> dx(delta_x);
  dx  = (KT.transpose() * y);
  memcpy(delta_x, dx.data(), EDIM * sizeof(double));
  err_fun(in_x, delta_x, x_new);
  Eigen::Matrix<double, DIM, 1> x(x_new);

  // update cov
  P = ((I_KH * P) * I_KH.transpose()) + ((KT.transpose() * R) * KT);

  // copy out state
  memcpy(in_x, x.data(), DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
  memcpy(in_z, y.data(), y.rows() * sizeof(double));
}




}
extern "C" {

void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_25, H_25, NULL, in_z, in_R, in_ea, MAHA_THRESH_25);
}
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<2, 3, 0>(in_x, in_P, h_24, H_24, NULL, in_z, in_R, in_ea, MAHA_THRESH_24);
}
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_30, H_30, NULL, in_z, in_R, in_ea, MAHA_THRESH_30);
}
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_26, H_26, NULL, in_z, in_R, in_ea, MAHA_THRESH_26);
}
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_27, H_27, NULL, in_z, in_R, in_ea, MAHA_THRESH_27);
}
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_29, H_29, NULL, in_z, in_R, in_ea, MAHA_THRESH_29);
}
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_28, H_28, NULL, in_z, in_R, in_ea, MAHA_THRESH_28);
}
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_31, H_31, NULL, in_z, in_R, in_ea, MAHA_THRESH_31);
}
void car_err_fun(double *nom_x, double *delta_x, double *out_2366717911037962719) {
  err_fun(nom_x, delta_x, out_2366717911037962719);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_70336108065318295) {
  inv_err_fun(nom_x, true_x, out_70336108065318295);
}
void car_H_mod_fun(double *state, double *out_281700328218384173) {
  H_mod_fun(state, out_281700328218384173);
}
void car_f_fun(double *state, double dt, double *out_3945758947465398650) {
  f_fun(state,  dt, out_3945758947465398650);
}
void car_F_fun(double *state, double dt, double *out_7239966002367196486) {
  F_fun(state,  dt, out_7239966002367196486);
}
void car_h_25(double *state, double *unused, double *out_4414103654617947245) {
  h_25(state, unused, out_4414103654617947245);
}
void car_H_25(double *state, double *unused, double *out_1365985619853648806) {
  H_25(state, unused, out_1365985619853648806);
}
void car_h_24(double *state, double *unused, double *out_218399050948173848) {
  h_24(state, unused, out_218399050948173848);
}
void car_H_24(double *state, double *unused, double *out_8020191077961834563) {
  H_24(state, unused, out_8020191077961834563);
}
void car_h_30(double *state, double *unused, double *out_7444812492615309208) {
  h_30(state, unused, out_7444812492615309208);
}
void car_H_30(double *state, double *unused, double *out_1236646672710408736) {
  H_30(state, unused, out_1236646672710408736);
}
void car_h_26(double *state, double *unused, double *out_442049788822243429) {
  h_26(state, unused, out_442049788822243429);
}
void car_H_26(double *state, double *unused, double *out_2375517699020407418) {
  H_26(state, unused, out_2375517699020407418);
}
void car_h_27(double *state, double *unused, double *out_3470593801716284810) {
  h_27(state, unused, out_3470593801716284810);
}
void car_H_27(double *state, double *unused, double *out_938116639090016175) {
  H_27(state, unused, out_938116639090016175);
}
void car_h_29(double *state, double *unused, double *out_7965145529649909723) {
  h_29(state, unused, out_7965145529649909723);
}
void car_H_29(double *state, double *unused, double *out_1746878017024800920) {
  H_29(state, unused, out_1746878017024800920);
}
void car_h_28(double *state, double *unused, double *out_5501663824664413576) {
  h_28(state, unused, out_5501663824664413576);
}
void car_H_28(double *state, double *unused, double *out_3335521000044729654) {
  H_28(state, unused, out_3335521000044729654);
}
void car_h_31(double *state, double *unused, double *out_5392762942373062487) {
  h_31(state, unused, out_5392762942373062487);
}
void car_H_31(double *state, double *unused, double *out_1396631581730609234) {
  H_31(state, unused, out_1396631581730609234);
}
void car_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
void car_set_mass(double x) {
  set_mass(x);
}
void car_set_rotational_inertia(double x) {
  set_rotational_inertia(x);
}
void car_set_center_to_front(double x) {
  set_center_to_front(x);
}
void car_set_center_to_rear(double x) {
  set_center_to_rear(x);
}
void car_set_stiffness_front(double x) {
  set_stiffness_front(x);
}
void car_set_stiffness_rear(double x) {
  set_stiffness_rear(x);
}
}

const EKF car = {
  .name = "car",
  .kinds = { 25, 24, 30, 26, 27, 29, 28, 31 },
  .feature_kinds = {  },
  .f_fun = car_f_fun,
  .F_fun = car_F_fun,
  .err_fun = car_err_fun,
  .inv_err_fun = car_inv_err_fun,
  .H_mod_fun = car_H_mod_fun,
  .predict = car_predict,
  .hs = {
    { 25, car_h_25 },
    { 24, car_h_24 },
    { 30, car_h_30 },
    { 26, car_h_26 },
    { 27, car_h_27 },
    { 29, car_h_29 },
    { 28, car_h_28 },
    { 31, car_h_31 },
  },
  .Hs = {
    { 25, car_H_25 },
    { 24, car_H_24 },
    { 30, car_H_30 },
    { 26, car_H_26 },
    { 27, car_H_27 },
    { 29, car_H_29 },
    { 28, car_H_28 },
    { 31, car_H_31 },
  },
  .updates = {
    { 25, car_update_25 },
    { 24, car_update_24 },
    { 30, car_update_30 },
    { 26, car_update_26 },
    { 27, car_update_27 },
    { 29, car_update_29 },
    { 28, car_update_28 },
    { 31, car_update_31 },
  },
  .Hes = {
  },
  .sets = {
    { "mass", car_set_mass },
    { "rotational_inertia", car_set_rotational_inertia },
    { "center_to_front", car_set_center_to_front },
    { "center_to_rear", car_set_center_to_rear },
    { "stiffness_front", car_set_stiffness_front },
    { "stiffness_rear", car_set_stiffness_rear },
  },
  .extra_routines = {
  },
};

ekf_lib_init(car)
