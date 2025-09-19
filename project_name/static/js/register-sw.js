if ('serviceWorker' in navigator) {
    navigator.serviceWorker
        .register("sw.js", { scope: '/' })
        .then(registration => {
            console.log("ServiceWorker running");
        })
        .catch(err => {
            console.log(err);
        })
}