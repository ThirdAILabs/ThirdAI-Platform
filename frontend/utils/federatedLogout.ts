import { signOut } from 'next-auth/react';

export default async function federatedLogout() {
  try {
    const response = await fetch('/api/auth/federated-logout');
    const data = await response.json();
    console.log('Data: ', data);
    if (response?.ok) {
      await signOut({ redirect: false });
      window.location.href = data.redirectUrl;
      return;
    }
    throw new Error(data.error);
  } catch (error) {
    console.log(error);
    alert(error);
    await signOut({ redirect: false });
    window.location.href = '/';
  }
}
