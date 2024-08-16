// ----------------------------------------------------------------------

export function createDeploymentUrl(deploymentId: string) {
    const hostname = process.env.DEPLOYMENT_BASE_URL;
    return `${hostname}/${deploymentId}`;
}

export function createTokenModelUrl(deploymentId: string) {
    const hostname = `${window.location.protocol}//${window.location.host}`;
    return `${hostname}/${deploymentId}`;
}
