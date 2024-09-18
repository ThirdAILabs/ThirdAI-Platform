// ----------------------------------------------------------------------

export function createDeploymentUrl(deploymentId: string) {
  const hostname = typeof window !== 'undefined' ? window.location.origin : '';
  return `${hostname}/${deploymentId}`;
}

export function createTokenModelUrl(deploymentId: string) {
  const hostname = typeof window !== 'undefined' ? window.location.origin : '';
  return `${hostname}/${deploymentId}`;
}
