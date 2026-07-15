export const THEME_STORAGE_KEY = "theme"

export const THEME_BLOCKING_SCRIPT = `(function(){try{var d=document.documentElement,t=localStorage.getItem("${THEME_STORAGE_KEY}")||"system";if(t==="system"){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}if(t==="dark"){d.classList.add("dark")}else{d.classList.remove("dark")}d.style.colorScheme=t}catch(e){}})();`
