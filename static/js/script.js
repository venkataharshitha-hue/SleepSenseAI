// Counter Animation

const counters =
document.querySelectorAll(".counter");

counters.forEach(counter=>{

    counter.innerText = "0";

    const updateCounter = ()=>{

        const target =
        +counter.getAttribute(
            "data-target"
        );

        const current =
        +counter.innerText;

        const increment =
        target / 100;

        if(current < target){

            counter.innerText =
            `${Math.ceil(
                current + increment
            )}`;

            setTimeout(
                updateCounter,
                20
            );

        }else{

            counter.innerText =
            target;

        }

    };

    updateCounter();

});

// Dark Mode

const toggle =
document.getElementById(
    "themeToggle"
);

if(toggle){

    toggle.addEventListener(
        "click",
        ()=>{

            document.body.classList.toggle(
                "dark-mode"
            );

        }
    );

}

// Delete Confirmation

function confirmDelete(){

    return confirm(
        "Are you sure?"
    );

}