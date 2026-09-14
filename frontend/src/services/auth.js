import api from './api';

export const loginUser = async (username, password, department) => {
  const payload = { username, password };
  if (department) {
    payload.department = department;
  }
  const response = await api.post('/auth/login', payload);
  const { access_token, user } = response.data;
  localStorage.setItem('abps_token', access_token);
  localStorage.setItem('abps_user', JSON.stringify(user));
  return user;
};

export const logoutUser = () => {
  localStorage.removeItem('abps_token');
  localStorage.removeItem('abps_user');
};

export const getCurrentUser = () => {
  const userStr = localStorage.getItem('abps_user');
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch (e) {
    return null;
  }
};
